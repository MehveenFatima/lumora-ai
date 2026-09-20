import pytest
from backend.app.services.question_quality_validator import (
    validate_question,
    check_verbatim_leakage,
    check_ngram_leakage,
    check_token_overlap,
    check_citation_leakage,
    check_source_dump,
    check_option_balance,
    ValidationResult,
    question_quality_validator,
)
from backend.app.services.question_generator import (
    GeneratedQuestionData,
    question_generator_service,
    QUESTION_TYPES,
)


class TestAntiLeakageValidation:
    """Tests verifying that question stems do not give away the answer or leak citations."""

    def test_verbatim_leakage_rejected(self):
        stem = "What function does TkRoot.new initialize in Ruby Tk applications?"
        answer = "TkRoot.new"
        has_leak, phrase = check_verbatim_leakage(stem, answer)
        assert has_leak is True
        assert "tkroot.new" in phrase.lower()

    def test_ngram_leakage_detected(self):
        stem = "When an application creates the primary root window and initializes the event loop, what widget is used?"
        answer = "Creates the primary root window and initializes the event loop"
        has_leak, phrase = check_ngram_leakage(stem, answer, n=4)
        assert has_leak is True
        assert phrase is not None

    def test_token_overlap_flags_excessive_overlap(self):
        stem = "How does TkRoot instantiate the graphical user interface main event loop display?"
        answer = "TkRoot instantiates the graphical user interface main event loop display"
        overlap = check_token_overlap(stem, answer, concept_name="TkRoot")
        assert overlap > 0.50

    def test_concept_name_allowed_without_leak_penalty(self):
        """Legitimate technical concepts (e.g. 'Binary Search Tree') in stem and answer must not trigger false positive."""
        stem = "What property defines the left subtree of a Binary Search Tree node?"
        answer = "Values strictly less than the Binary Search Tree node key"
        overlap = check_token_overlap(stem, answer, concept_name="Binary Search Tree")
        assert overlap < 0.45

    def test_citation_leakage_detected(self):
        """Questions containing .pdf, page numbers, or doc references in the stem must be rejected."""
        stem = "How does SSL-UNIT - 1 (1).pdf characterize Example on Page 37?"
        answer = "It demonstrates initialization of Tk window"
        has_leak, matches = check_citation_leakage(stem, answer)
        assert has_leak is True
        assert any(".pdf" in m.lower() or "page" in m.lower() for m in matches)

    def test_source_dump_code_snippet_detected(self):
        """Raw source dumps in question stems must be flagged."""
        stem = "What does the following snippet accomplish: require 'tk' root = TkRoot.new { title 'Hello' } Tk.mainloop?"
        has_dump, reason = check_source_dump(stem)
        assert has_dump is True
        assert "code" in reason.lower() or "token" in reason.lower()

    def test_option_balance_flags_extreme_length_difference(self):
        """Flag when correct answer is unnaturally longer than distractors."""
        options = [
            {"key": "A", "text": "Short"},
            {"key": "B", "text": "Tiny"},
            {"key": "C", "text": "Minimal"},
            {"key": "D", "text": "This is an extraordinarily verbose and exhaustive correct answer that easily stands out as correct because of its length compared to the tiny distractors."},
        ]
        is_balanced, reason = check_option_balance(options, "D")
        assert is_balanced is False
        assert ("longer" in reason.lower() or "length" in reason.lower())

    def test_valid_conceptual_question_passes_quality_check(self):
        """A well-formed conceptual question with balanced options and zero leakage must pass with high score."""
        stem = "What primary architectural responsibility is assigned to TkRoot in Ruby Tk GUI development?"
        options = [
            {"key": "A", "text": "Constructs the primary application window and initializes the widget hierarchy."},
            {"key": "B", "text": "Compiles Ruby source bytecode into native graphical primitives."},
            {"key": "C", "text": "Dispatches asynchronous network requests for remote UI widgets."},
            {"key": "D", "text": "Manages SQL database connections for desktop GUI state."},
        ]
        correct_key = "A"
        concept = "TkRoot"

        result = validate_question(
            question_text=stem,
            options=options,
            correct_key=correct_key,
            concept_name=concept,
            document_name="SSL-UNIT - 1 (1).pdf",
            page_number=37,
        )
        assert result.is_valid is True
        assert result.quality_score >= 0.70
        assert result.leakage_score <= 0.10
        assert len(result.rejection_reasons) == 0

    def test_flawed_ssl_example_question_is_strictly_rejected(self):
        """The exact flawed question from the live incident must be rejected by validate_question."""
        flawed_stem = "How does SSL-UNIT - 1 (1).pdf characterize Example on Page 37 with respect to 'Example 4 require \'tk\' root = TkRoot.new ...'?"
        options = [
            {"key": "A", "text": "require 'tk' root = TkRoot.new { title 'Hello World' }"},
            {"key": "B", "text": "Unrelated option B"},
            {"key": "C", "text": "Unrelated option C"},
            {"key": "D", "text": "Unrelated option D"},
        ]
        result = validate_question(
            question_text=flawed_stem,
            options=options,
            correct_key="A",
            concept_name="TkRoot",
            document_name="SSL-UNIT - 1 (1).pdf",
            page_number=37,
        )
        assert result.is_valid is False
        assert result.quality_score < 0.70
        assert len(result.rejection_reasons) > 0
        assert any("citation" in v.lower() or "leakage" in v.lower() or "verbatim" in v.lower() for v in result.rejection_reasons)

    def test_exact_broken_cgi_question_is_strictly_rejected(self):
        """
        Regression Test for FAILURE 2:
        Question: 'What core architectural responsibility is fulfilled by Basics of CGI Scripts in application development?'
        Correct answer: 'Here's how to read form values.'
        MUST be rejected for instructional heading answer, concept prefix, and semantic incompatibility.
        """
        stem = "What core architectural responsibility is fulfilled by Basics of CGI Scripts in application development?"
        options = [
            {"key": "A", "text": "Here's how to read form values."},
            {"key": "B", "text": "Bypasses runtime execution flow to render output without initializing necessary object state."},
            {"key": "C", "text": "Directly reinterprets byte-level instructions without dispatching standard event handlers."},
            {"key": "D", "text": "Dispatches unmanaged asynchronous callbacks without binding to application scope."},
        ]
        result = validate_question(
            question_text=stem,
            options=options,
            correct_key="A",
            concept="Basics of CGI Scripts",
            topic="Ruby Web Development",
        )
        assert result.is_valid is False
        assert len(result.rejection_reasons) > 0
        # Verify specific rejection reasons
        has_inst = any("instructional" in r.lower() or "tutorial" in r.lower() for r in result.rejection_reasons)
        has_prefix = any("basics of" in r.lower() or "division" in r.lower() for r in result.rejection_reasons)
        has_compat = any("responsibility" in r.lower() or "semantic" in r.lower() for r in result.rejection_reasons)
        assert has_inst or has_prefix or has_compat

    def test_code_syntax_leakage_imbalance_rejected(self):
        """
        When question is conceptual and correct answer uniquely contains code syntax
        while distractors are plain prose, it must be rejected for code token leakage.
        """
        stem = "What primary operational role is fulfilled by Parameter Parser in web requests?"
        options = [
            {"key": "A", "text": "params['username'] = sanitize(input)"},
            {"key": "B", "text": "Validates incoming HTTP session headers and token state."},
            {"key": "C", "text": "Coordinates database query caching across execution threads."},
            {"key": "D", "text": "Serializes response bodies into standard wire representations."},
        ]
        result = validate_question(
            question_text=stem,
            options=options,
            correct_key="A",
            concept="Parameter Parser",
        )
        assert result.is_valid is False
        assert any("code" in r.lower() or "syntax" in r.lower() or "imbalance" in r.lower() for r in result.rejection_reasons)

    def test_legitimate_code_syntax_question_is_accepted(self):
        """
        Positive test: When the question stem genuinely asks about code or syntax,
        and all answer choices are code expressions, the question MUST be accepted.
        """
        stem = "Which code syntax is used to bind an event command block to a TkButton in Ruby?"
        options = [
            {"key": "A", "text": "button.command { puts 'Clicked' }"},
            {"key": "B", "text": "button.on_click { puts 'Clicked' }"},
            {"key": "C", "text": "button.bind_action { puts 'Clicked' }"},
            {"key": "D", "text": "button.attach_event { puts 'Clicked' }"},
        ]
        result = validate_question(
            question_text=stem,
            options=options,
            correct_key="A",
            concept="TkButton Event Binding",
            topic="Ruby GUI",
            question_type="application",
        )
        assert result.is_valid is True
        assert result.quality_score >= 0.70
        assert len(result.rejection_reasons) == 0



class TestQuestionGeneratorAntiLeakage:
    """Tests that GeneratedQuestionData and candidate generation enforce quality standards."""

    def test_generated_question_data_includes_quality_fields(self):
        q = GeneratedQuestionData(
            topic="Ruby GUI",
            concept="TkRoot",
            difficulty=2,
            question_text="What is the role of TkRoot in Ruby Tk?",
            options=[
                {"key": "A", "text": "Creates the root application window."},
                {"key": "B", "text": "Manages network sockets."},
                {"key": "C", "text": "Formats strings."},
                {"key": "D", "text": "Parses XML documents."},
            ],
            correct_option="A",
            explanation="TkRoot is the top-level window widget.",
            fingerprint="test_fp_123",
            question_type="conceptual",
            quality_score=0.92,
            leakage_score=0.0,
        )
        assert q.question_type == "conceptual"
        assert q.quality_score == 0.92
        assert q.leakage_score == 0.0

    def test_question_types_are_diverse(self):
        expected_types = [
            "conceptual", "comparison", "application", "scenario",
            "reasoning", "trace_output", "interpretation", "edge_case",
            "complexity_analysis",
        ]
        for t in expected_types:
            assert t in QUESTION_TYPES

    @pytest.mark.asyncio
    async def test_candidate_generation_filters_leaky_questions(self):
        """Simulate candidate generation and verify candidates have valid quality scores and no citation leaks."""
        sample_chunks = [
            {
                "id": "doc_chunk_1",
                "document_id": "doc_1",
                "document_name": "SSL-UNIT - 1 (1).pdf",
                "page_number": 37,
                "content": "Ruby Tk provides GUI capabilities. TkRoot creates the primary window and event loop for widgets. Example 4 shows how TkRoot is initialized with title and geometry.",
            },
            {
                "id": "doc_chunk_2",
                "document_id": "doc_1",
                "document_name": "SSL-UNIT - 1 (1).pdf",
                "page_number": 38,
                "content": "TkButton allows user interaction. Event handlers are bound via command blocks. TkLabel displays static or dynamic text inside the frame.",
            },
        ]

        candidates = await question_generator_service.generate_candidate_pool(
            workspace_id="test_ws",
            target_count=5,
            excluded_fingerprints=set(),
            target_concepts=["TkRoot", "TkButton"],
            preferred_difficulty=2,
            chunks=sample_chunks,
        )

        assert len(candidates) >= 2
        for q in candidates:
            # 1. Stem must not contain .pdf or Page citation references
            assert ".pdf" not in q.question_text.lower()
            assert "page " not in q.question_text.lower()
            # 2. Quality score must be >= 0.70
            assert q.quality_score >= 0.70
            # 3. Leakage score must be acceptable (< 0.35)
            assert q.leakage_score < 0.35
            # 4. Question type must be one of the recognized types
            assert q.question_type in QUESTION_TYPES
            # 5. Citation metadata must be separated
            assert q.document_name == "SSL-UNIT - 1 (1).pdf"
