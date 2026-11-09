# frozen_string_literal: true

require_relative "lib/oude_mechanismen/version"

Gem::Specification.new do |spec|
  spec.name          = "oude-mechanismen"
  spec.version       = OudeMechanismen::VERSION
  spec.authors       = ["Estevão Alvarenga"]
  spec.email         = ["estevao.alvarenga@gmail.com"]

  spec.summary       = "Shared procedural engine and Jekyll tooling for campaign vaults."
  spec.description   = "Oude Mechanismen provides static data extraction, semantic catalogue generation, and agentic workflows for tabletop RPG campaign vaults."
  spec.homepage      = "https://github.com/terra-campaigns/oude-mechanismen"
  spec.license       = "MIT"
  spec.required_ruby_version = ">= 3.0.0"

  spec.metadata["source_code_uri"] = spec.homepage
  spec.metadata["changelog_uri"] = "#{spec.homepage}/blob/main/CHANGELOG.md"

  spec.files = Dir.chdir(__dir__) do
    `git ls-files -z`.split("\x0").reject do |f|
      (File.expand_path(f) == __FILE__) ||
        f.start_with?("tests/", "spec/", ".git", ".github", "state/")
    end
  end
  spec.require_paths = ["lib"]

  spec.add_dependency "jekyll", ">= 4.0"
end
