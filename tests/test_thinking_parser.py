from backend.services.thinking_parser import (
    MAX_THINKING_LENGTH,
    StreamingThinkingParser,
    THINKING_TRUNCATION_SUFFIX,
    parse_reasoning_api_response,
    parse_thinking_response,
)


def test_parse_thinking_response_with_both_sections():
    result = parse_thinking_response(
        "<thinking>\nStep 1\nStep 2\n</thinking>\n<final>\nFinal answer\n</final>"
    )

    assert result.thinking == "Step 1\nStep 2"
    assert result.final_answer == "Final answer"
    assert result.raw.startswith("<thinking>")


def test_parse_thinking_response_falls_back_when_tags_missing():
    result = parse_thinking_response("Plain response without tags.")

    assert result.thinking is None
    assert result.final_answer == "Plain response without tags."


def test_parse_thinking_response_falls_back_when_thinking_tag_is_unclosed():
    result = parse_thinking_response("<thinking>unfinished\n<final>Visible answer</final>")

    assert result.thinking is None
    assert result.final_answer == "<thinking>unfinished\n<final>Visible answer</final>"


def test_parse_thinking_response_uses_remaining_content_when_final_tag_missing():
    result = parse_thinking_response("<thinking>Reasoning</thinking>\nAnswer body")

    assert result.thinking == "Reasoning"
    assert result.final_answer == "Answer body"


def test_parse_thinking_response_recovers_when_final_closing_tag_is_missing():
    result = parse_thinking_response("<thinking>Reasoning</thinking>\n<final>Answer body")

    assert result.thinking == "Reasoning"
    assert result.final_answer == "Answer body"


def test_parse_thinking_response_truncates_long_thinking():
    long_thinking = "a" * (MAX_THINKING_LENGTH + 50)

    result = parse_thinking_response(f"<thinking>{long_thinking}</thinking><final>Done</final>")

    assert result.final_answer == "Done"
    assert result.thinking is not None
    assert len(result.thinking) == MAX_THINKING_LENGTH
    assert result.thinking.endswith(THINKING_TRUNCATION_SUFFIX)


def test_parse_reasoning_api_response_maps_reasoning_fields():
    result = parse_reasoning_api_response(
        {
            "reasoning_content": "Model reasoning",
            "content": "Visible answer",
        }
    )

    assert result.thinking == "Model reasoning"
    assert result.final_answer == "Visible answer"


def test_streaming_thinking_parser_splits_channels_incrementally():
    parser = StreamingThinkingParser()

    chunks = []
    chunks.extend(parser.feed("<think"))
    chunks.extend(parser.feed("ing>Plan A"))
    chunks.extend(parser.feed("</thinking><final>Answer"))
    chunks.extend(parser.flush())

    assert [(chunk.channel, chunk.text) for chunk in chunks] == [
        ("thinking", "Plan A"),
        ("final", "Answer"),
    ]


def test_streaming_thinking_parser_routes_prefix_to_thinking_before_first_tag():
    parser = StreamingThinkingParser()

    chunks = []
    chunks.extend(parser.feed("Prelude"))
    chunks.extend(parser.feed("<thinking>Plan</thinking><final>Answer</final>"))
    chunks.extend(parser.flush())

    assert [(chunk.channel, chunk.text) for chunk in chunks] == [
        ("thinking", "PreludePlan"),
        ("final", "Answer"),
    ]


def test_streaming_thinking_parser_streams_plain_text_without_tags():
    parser = StreamingThinkingParser()

    chunks = []
    chunks.extend(parser.feed("Plain "))
    chunks.extend(parser.feed("response"))
    chunks.extend(parser.flush())

    assert "".join(chunk.text for chunk in chunks if chunk.channel == "final") == "Plain response"
