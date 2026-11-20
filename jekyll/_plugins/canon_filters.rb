# frozen_string_literal: true

# jekyll/_plugins/canon_filters.rb — Published-canon delivery policy filters (#20, #18).
#
# - read_aloud_filter: strips boxed read-aloud text (`> Table Read-Aloud` /
#   `> **Read-Aloud**` blockquote blocks) so it can never reach published HTML.
# - narrative_link_filter: renders mechanical episode parentheticals
#   (`(See Episode 3)`) as a fallback badge span, leaving genuine narrative
#   markdown links untouched.

module OudeMechanismen
  module CanonFilters
    READ_ALOUD_BLOCK_RE = /(?:^|\n)(>[ \t]*\**\s*(?:Table[ \t]+)?Read[- ]?Aloud\b[^\n]*\n(?:[ \t]*>[ \t]*[^\n]*\n?)*)/i

    # Mechanical parenthetical episode references, e.g. "(See Episode 3)".
    MECHANICAL_PAREN_RE = /\((?:see|cf\.|refer to)[ \t]+(?:episode|ep\.?|session)[ \t]+([0-9a-zA-Z_\-]+)\)/i

    def read_aloud_filter(input)
      return input if input.nil?
      input.to_s.gsub(READ_ALOUD_BLOCK_RE, "")
    end

    def narrative_link_filter(input)
      return input if input.nil?
      input.to_s.gsub(MECHANICAL_PAREN_RE) do
        num = Regexp.last_match(1)
        %(<span class="episode-ref episode-ref-unresolved" data-episode="#{num}">Episode #{num}</span>)
      end
    end
  end
end

Liquid::Template.register_filter(OudeMechanismen::CanonFilters) if defined?(Liquid)
