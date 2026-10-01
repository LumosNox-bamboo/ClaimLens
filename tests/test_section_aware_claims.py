from claimlens.claims import extract_claims


def test_section_aware_mixed_cv_extraction():
    text = """个人概况 Research OS AI4Science 多智能体系统。
教育经历 2023.10–至今 Example University｜医学 博士研究生 2020.09–2023.07 Example Medical College｜医学 硕士
核心研究能力与特色 大样本机器学习研究发表于 Example Medicine。
代表性论文 1. A. Author. Synthetic cohort study. Example Medicine. 2026. DOI: 10.1234/ABC.1. 2. B. Author. Another study. Accepted 2026.
在研第一作者论文 • A Synthetic Pending Study About Pain Outcomes. • Another Synthetic Pending Study About Cohorts.
人工智能与科研系统开发 01｜Research OS｜科研工作台。 02｜AI Agent｜挑战赛工作流。
荣誉、竞赛与学术奖励 2026 Example Innovation Competition 第二名。 2025 Example Society 大会优秀壁报。 本科及硕士毕业均获上海市优秀毕业生（Top 2%）。
国际学术交流 2026｜Example World Congress, Berlin｜口头报告及壁报展示。
专业资质与培训经历 医师资格：已取得医师资格证书；专业资质：Example ICD-11 课程；Example Training 培训。 临床心理实践：示例经历。 语言：中文。"""
    claims = extract_claims(text, "C-SYN", ".pdf")
    types = [c.claim_type for c in claims]
    assert types.count("education") == 2
    assert types.count("publication") == 2
    assert types.count("working_paper") == 2
    assert types.count("conference_presentation") == 1
    assert "professional_qualification" in types
    assert "certification" in types
    assert not any(
        "Research OS" in c.claim_text or "AI Agent" in c.claim_text for c in claims
    )


def test_working_papers_are_local_only():
    text = "在研第一作者论文 • A Synthetic Pending Manuscript About Pain."
    claims = extract_claims(text, "C-SYN")
    assert len(claims) == 1
    assert claims[0].verification_scope == "self_reported"
    assert claims[0].verification_priority == "low"


def test_education_date_range_kept_together():
    text = (
        "教育经历 2020.09–2023.07 Example University｜医学 硕士 "
        "2015.09–2020.07 Example College｜医学 学士"
    )
    claims = extract_claims(text, "C-SYN")
    assert [c.year for c in claims] == ["2020", "2015"]
    assert "2020.09–2023.07" in claims[0].claim_text


def test_special_award_wording_is_kept():
    text = (
        "荣誉、竞赛与学术奖励 2025 Example Society 学术年会大会优秀壁报。 "
        "本科及硕士毕业均获上海市优秀毕业生（Top 2%）。"
    )
    claims = extract_claims(text, "C-SYN")
    assert len(claims) == 2
    assert all(c.claim_type == "award" for c in claims)


def test_doi_terminal_number_is_not_treated_as_list_item():
    text = (
        "代表性论文 1. Synthetic study. Example Medicine. 2026. "
        "DOI: 10.1186/s12916-026-04851-7. "
        "2. Another synthetic study. Example Journal. 2025."
    )
    claims = extract_claims(text, "C-SYN")
    assert len(claims) == 2
    assert claims[0].doi == "10.1186/s12916-026-04851-7"
