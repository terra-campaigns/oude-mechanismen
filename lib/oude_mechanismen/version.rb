# frozen_string_literal: true

module OudeMechanismen
  VERSION_FILE = File.expand_path("../../VERSION", __dir__)
  VERSION = if File.exist?(VERSION_FILE)
              File.read(VERSION_FILE).strip
            else
              "0.5.2"
            end
end
