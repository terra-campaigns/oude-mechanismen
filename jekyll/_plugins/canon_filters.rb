# frozen_string_literal: true

# jekyll/_plugins/canon_filters.rb — Published-canon delivery policy (#20, #18).
#
# - read_aloud_filter: strips boxed read-aloud text (`> Table Read-Aloud` /
#   `> **Read-Aloud**` blockquote blocks, any nesting depth) from rendered output.
# - narrative_link_filter: renders mechanical episode parentheticals
#   (`(See Episode 3)`) as fallback badge spans, leaving genuine narrative
#   markdown links untouched.
#
# The filters are registered as Liquid filters for template authors AND applied
# automatically to every rendered page/document output via a :post_render hook,
# so the policy holds regardless of vault layout.
#
# NOTE: keep the markdown regexes aligned with scripts/lint_wiki.py
# (READ_ALOUD_LINE_RE / MECHANICAL_PAREN_RE) so every lint-flagged form is also
# stripped/flagged at render time.

module OudeMechanismen
  module CanonFilters
    # Read-aloud blockquote block in markdown: header line anywhere (indented,
    # nested `>>`), optional trailing newline at EOF, continuation lines at any
    # quote depth.
    READ_ALOUD_BLOCK_RE = /(?:^|\n)[ \t]*(?:>[ \t]*)+\**\s*(?:Table[ \t]+)?Read[- ]?Aloud\b[^\n]*(?:\n|\z)(?:[ \t]*(?:>[ \t]*)+[^\n]*\n?)*/i

    # Rendered-HTML form: kramdown converts the blockquote before :post_render,
    # so the hook also strips <blockquote> blocks whose first paragraph is a
    # read-aloud marker.
    READ_ALOUD_HTML_RE = /<blockquote>\s*<p>[^<]*(?:<[^>]+>[^<]*)*\**\s*(?:Table[ \t]+)?Read[- ]?Aloud\b[\s\S]*?<\/blockquote>/i

    # Mechanical parenthetical episode references with a numeric-ish token,
    # e.g. "(See Episode 3)" or "(see ep_012)". Ordinary prose such as
    # "(see session notes)" must NOT match.
    MECHANICAL_PAREN_RE = /\((?:see|cf\.|refer to)[ \t]+(?:episode|ep\.?|session)[ \t]+([0-9]+[a-z]?|_?[0-9a-z]+_[0-9]+)\)/i

    def read_aloud_filter(input)
      return input if input.nil?
      input.to_s.gsub(READ_ALOUD_BLOCK_RE) { |m| m.start_with?("\n") ? "\n" : "" }
    end

    def narrative_link_filter(input)
      return input if input.nil?
      input.to_s.gsub(MECHANICAL_PAREN_RE) do
        num = Regexp.last_match(1)
        %(<span class="episode-ref episode-ref-unresolved" data-episode="#{num}">Episode #{num}</span>)
      end
    end

    def self.apply_canon_policy(output)
      obj = Object.new.extend(CanonFilters)
      output = obj.read_aloud_filter(output)
      output = output.gsub(READ_ALOUD_HTML_RE, "")
      obj.narrative_link_filter(output)
    end
  end
end

Liquid::Template.register_filter(OudeMechanismen::CanonFilters) if defined?(Liquid)

if defined?(Jekyll) && defined?(Jekyll::Hooks)
  Jekyll::Hooks.register [:pages, :documents], :post_render do |item|
    next unless item.respond_to?(:output) && item.output.is_a?(String)
    item.output = OudeMechanismen::CanonFilters.apply_canon_policy(item.output)
  end
end
