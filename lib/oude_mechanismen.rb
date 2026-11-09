# frozen_string_literal: true

require "jekyll"
require_relative "oude_mechanismen/version"

# Load Jekyll plugins from engine
require_relative "../jekyll/_plugins/data_extractor"
require_relative "../jekyll/_plugins/llm_content"

module OudeMechanismen
  INCLUDES_PATH = File.expand_path("../jekyll/_includes", __dir__)
end

if defined?(Jekyll)
  Jekyll::Hooks.register :site, :after_reset do |site|
    if Dir.exist?(OudeMechanismen::INCLUDES_PATH)
      site.includes_load_paths << OudeMechanismen::INCLUDES_PATH unless site.includes_load_paths.include?(OudeMechanismen::INCLUDES_PATH)
    end
  end
end
