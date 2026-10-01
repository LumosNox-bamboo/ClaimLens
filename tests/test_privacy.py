from claimlens.privacy import detect_pii, redact_text


def kinds(text): return {x.kind for x in detect_pii(text)}


def test_english_pii():
    text = "Name: Jane Example\nDate of Birth: 1991-02-03\nEmail: jane@example.test\nPhone: +49 6221 555123\nAddress: 12 Example Road, Test City"
    found = kinds(text)
    assert {"english_name", "dob", "email", "phone", "address"} <= found
    out, _ = redact_text(text, "verification")
    assert "Jane Example" not in out and "jane@example.test" not in out


def test_chinese_pii():
    text = "姓名：李小明\n出生日期：1992年3月4日\n手机：13812345678\n身份证号码：110105199203041234\n通信地址：示例省示例市测试路88号\nQQ：12345678\n微信号：Test_user88"
    found = kinds(text)
    assert {"chinese_name", "dob", "phone", "chinese_id", "address", "qq", "wechat"} <= found
    out, _ = redact_text(text, "strict")
    assert "李小明" not in out and "110105199203041234" not in out


def test_mixed_and_passport():
    text = "姓名：王测试 / Name: Alice Test\nPassport No: E12345678\nTelegram: @alice_test\nEmail alice@test.example"
    found = kinds(text)
    assert {"chinese_name", "passport", "telegram", "email"} <= found


def test_custom_mode_can_keep_or_remove_selected_fields():
    text = "Email: person@example.test\nPhone: +1 202 555 0123"
    out, _ = redact_text(text, "custom", remove=["email"])
    assert "person@example.test" not in out
    assert "202 555 0123" in out


def test_strict_removes_claim_author_list_but_verification_preserves_it():
    text = "Authors: Alice Example, Bob Synthetic"
    strict, _ = redact_text(text, "strict")
    verification, _ = redact_text(text, "verification")
    assert "Alice Example" not in strict
    assert "Alice Example" in verification
