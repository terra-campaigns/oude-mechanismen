# frozen_string_literal: true

# Headless integration coverage for the *packaged* dynamic gem (issue #23).
#
# The fixture-vault `bundle exec jekyll build` and clean-venv wheel smoke for
# issue #34 live in the Python suites of PR #86 (`tests/test_e2e_jekyll.py`,
# `tests/test_e2e_wheel.py`, run inside the CI `validate` job). This suite
# covers what those cannot: the built gem artefact itself, in isolation.
#
# JekyllHeadlessTest verifies:
#   1. `gem build` archives bundle the engine assets (lib/, jekyll/_plugins/,
#      jekyll/_includes/) and no repository clutter (tests/, .github/);
#   2. the installed gem loads in isolation from a scratch GEM_HOME
#      (`require "oude-mechanismen"` resolves the plugin and includes from
#      the installed gem, not the checkout);
#   3. a real headless `jekyll build` of tests/fixtures/vault/ driven by that
#      installed gem renders layouts and gem-served includes, populates
#      site.data via _plugins/data_extractor.rb, and writes
#      .agents/context/catalog.json with the engine version stamp.
#
# Run locally with:  gem install --no-document jekyll -v '~> 4.4.1'
#                    ruby tests/test_dynamic_gem.rb
# CI runs this via the `validate` job in .github/workflows/ci.yml.

require "minitest/autorun"
require "fileutils"
require "tmpdir"
require "json"
require "open3"
require "rbconfig"
require "rubygems"
require "rubygems/package"

REPO_ROOT = File.expand_path("..", __dir__)
VERSION = File.read(File.join(REPO_ROOT, "VERSION"), encoding: "utf-8").strip
FIXTURE_VAULT = File.join(REPO_ROOT, "tests", "fixtures", "vault")

class JekyllHeadlessTest < Minitest::Test
  def setup
    jekyll_spec = Gem::Specification.find_all_by_name("jekyll").max_by(&:version)
    if jekyll_spec.nil?
      skip "jekyll gem not installed; run: gem install --no-document jekyll -v '~> 4.4.1'"
    end
    @jekyll_exe = jekyll_spec.bin_file("jekyll")
    @tmp = Dir.mktmpdir("oude-gem-e2e-")
    @gem_home = File.join(@tmp, "gem_home")
    FileUtils.mkdir_p(@gem_home)
    @gem_file = File.join(@tmp, "oude-mechanismen-#{VERSION}.gem")
    build_gem
    install_gem_isolated
    @vault = File.join(@tmp, "vault")
    FileUtils.cp_r(FIXTURE_VAULT, @vault)
  end

  def teardown
    FileUtils.remove_entry(@tmp) if @tmp && File.directory?(@tmp)
  end

  def test_gem_archive_bundles_engine_assets
    contents = Gem::Package.new(@gem_file).contents
    %w[
      lib/oude-mechanismen.rb
      lib/oude_mechanismen.rb
      lib/oude_mechanismen/version.rb
      jekyll/_plugins/data_extractor.rb
      jekyll/_includes/connected_to.html
      jekyll/_includes/header_chapter.md
      jekyll/_includes/header_directories.md
      jekyll/_includes/image_gallery.html
    ].each do |file|
      assert_includes contents, file, "gem archive is missing #{file}"
    end
    refute contents.any? { |f| f.start_with?("tests/", "spec/", ".github/", ".git") },
           "gem archive must not bundle repository clutter"
  end

  def test_gem_loads_in_isolation
    out, err, status = Open3.capture3(isolated_env, RbConfig.ruby, "-e", <<~RUBY)
      require "oude-mechanismen"
      abort "data extractor plugin not loaded" unless defined?(Jekyll::DataExtractorGenerator)
      abort "includes path outside scratch GEM_HOME" unless OudeMechanismen::INCLUDES_PATH.start_with?(#{@gem_home.dump})
      abort "bundled includes missing" unless Dir.exist?(OudeMechanismen::INCLUDES_PATH)
      puts OudeMechanismen::VERSION
    RUBY
    assert status.success?, "isolated gem load failed:\n#{out}\n#{err}"
    assert_equal VERSION, out.strip
  end

  def test_headless_build_with_installed_gem
    out, err, status = Open3.capture3(isolated_env, RbConfig.ruby, @jekyll_exe, "build", chdir: @vault)
    assert status.success?, "headless jekyll build with the installed gem failed:\n#{out}\n#{err}"
    site = File.join(@vault, "_site")

    index = File.read(File.join(site, "index.html"), encoding: "utf-8")
    assert_includes index, "<body>", "layout was not applied to index.md"
    assert_includes index, "Fixture Home", "page content was not rendered"

    alpha = File.read(File.join(site, "directory", "alpha", "index.html"), encoding: "utf-8")
    assert_includes alpha, "campaigns/ep_001.md", "site.data.markdown_links was not rendered into the page"
    assert_includes alpha, "Chapters", "gem-served include connected_to.html was not rendered"

    refute File.exist?(File.join(site, "all-content.html")),
           "engine synthesised _site/all-content.html; the generator was retired in #25/#35"

    catalog = JSON.parse(File.read(File.join(@vault, ".agents", "context", "catalog.json"), encoding: "utf-8"))
    assert_equal VERSION, catalog["engine_version"], "catalog.json missing the engine version stamp"
    assert_equal 2, catalog["total_entries"], "catalog.json should index the two Tier 1 fixture notes"
    paths = catalog["entries"].map { |e| e["path"] }
    assert_includes paths, "directory/alpha.md"
    assert_includes paths, "campaigns/ep_001.md"
    alpha_entry = catalog["entries"].find { |e| e["path"] == "directory/alpha.md" }
    assert_includes alpha_entry["links_out"], "campaigns/ep_001.md"
    assert_includes alpha_entry["links_in"], "index.md"
  end

  private

  def build_gem
    out, err, status = Open3.capture3("gem", "build", "oude-mechanismen.gemspec", "--output", @gem_file, chdir: REPO_ROOT)
    assert status.success?, "gem build failed:\n#{out}\n#{err}"
    assert File.file?(@gem_file), "gem build produced no archive at #{@gem_file}"
  end

  def install_gem_isolated
    out, err, status = Open3.capture3(
      "gem", "install", "--local", "--ignore-dependencies", "--no-document",
      "--install-dir", @gem_home, @gem_file
    )
    assert status.success?, "gem install into scratch GEM_HOME failed:\n#{out}\n#{err}"
  end

  # The scratch GEM_HOME holds only the built oude-mechanismen gem; every other
  # gem (jekyll and its dependencies) resolves from the ambient gem paths. The
  # -I pin via RUBYOPT makes `require "oude-mechanismen"` load from the scratch
  # install even when another copy is visible in the ambient GEM_PATH (RubyGems
  # otherwise activates the highest visible version).
  def isolated_env
    gem_lib = File.join(@gem_home, "gems", "oude-mechanismen-#{VERSION}", "lib")
    {
      "GEM_HOME" => @gem_home,
      "GEM_PATH" => ([@gem_home] + Gem.path).join(File::PATH_SEPARATOR),
      "RUBYOPT" => "-I#{gem_lib}"
    }
  end
end
