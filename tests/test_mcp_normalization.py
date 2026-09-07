from incident_commander.graph import normalize_mcp_result


def test_mcp_text_json_is_normalized_to_dict():
    result = [
        {
            "type": "text",
            "text": '{"executed":true,"action":"scale_out"}',
        }
    ]
    normalized = normalize_mcp_result(result)
    assert normalized == {"executed": True, "action": "scale_out"}

