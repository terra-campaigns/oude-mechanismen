# frozen_string_literal: true

module Jekyll
  module LlmContentFilter
    def raw_markdown(page)
      return "" unless page['path']

      begin
        content = File.read(page['path'], encoding: 'utf-8')

        # Strip YAML front matter
        if content =~ /\A---\s*\n.*?\n---\s*\n/m
          content = content.sub(/\A---\s*\n.*?\n---\s*\n/m, '')
        end

        # Remove liquid includes, comments, and other structural jekyll tags that add noise
        content = content.gsub(/{%\s*include\s+.*?%}/, '')
        content = content.gsub(/{%\s*comment\s*%}.*?{%\s*endcomment\s*%}/m, '')

        # Remove Kramdown IALs like {: .text-right }
        content = content.gsub(/\{:\s*\..*?\s*\}/, '')

        content.strip
      rescue
        ""
      end
    end
  end
end

Liquid::Template.register_filter(Jekyll::LlmContentFilter)

if defined?(Jekyll) && defined?(Jekyll::PageWithoutAFile) && defined?(Jekyll::Generator)
  module Jekyll
    class LlmContentPage < PageWithoutAFile
      def initialize(site, base, dir, name, template_content)
        super(site, base, dir, name)
        self.data = {
          "layout" => nil,
          "permalink" => "/all-content.html",
          "sitemap" => false
        }
        self.content = template_content
      end
    end

    class LlmContentGenerator < Generator
      safe true
      priority :low

      def generate(site)
        return if site.pages.any? { |p| p.url == "/all-content.html" || p.name == "all-content.md" }

        template_path = File.expand_path("../all-content.md", __dir__)
        return unless File.exist?(template_path)

        template_content = File.read(template_path, encoding: "utf-8")

        # Strip YAML front matter if present
        if template_content =~ /\A---\s*\n.*?\n---\s*\n/m
          template_content = template_content.sub(/\A---\s*\n.*?\n---\s*\n/m, "")
        end

        site.pages << LlmContentPage.new(site, site.source, "", "all-content.md", template_content)
      end
    end
  end
end
