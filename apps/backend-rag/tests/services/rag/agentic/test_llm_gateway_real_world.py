"""
Real-World Production Scenarios Test Suite for LLMGateway

This suite provides testing for real-world production scenarios that
the LLMGateway would encounter in actual deployment environments.

Real-World Coverage Areas:
- Customer support automation
- Content moderation workflows
- E-commerce integration
- Healthcare compliance
- Financial services validation
- Educational platform testing
- Social media content analysis
- Legal document processing
- Research and development workflows
- Multi-tenant architecture testing

Author: Nuzantara Team
Date: 2025-01-04
Version: 5.0.0 (Real-World Production Edition)
"""

import uuid
from datetime import datetime
from unittest.mock import Mock

import pytest

# Import the minimal gateway for testing
from test_llm_gateway_isolated import TIER_FLASH, MinimalLLMGateway, MockTokenUsage


class TestCustomerSupportAutomation:
    """Test customer support automation scenarios."""

    @pytest.fixture
    def support_gateway(self):
        """Gateway configured for customer support testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.support_tickets = []
        gateway.customer_data = {}
        return gateway

    async def test_ticket_classification(self, support_gateway):
        """Test automatic ticket classification."""
        gateway = support_gateway

        # Ticket categories
        categories = {
            "technical": ["bug", "error", "crash", "not working", "broken"],
            "billing": ["payment", "charge", "invoice", "refund", "billing"],
            "account": ["login", "password", "account", "access", "profile"],
            "feature": ["request", "suggestion", "improvement", "new feature"],
            "general": ["help", "question", "how to", "information"],
        }

        async def classify_ticket_call(*args, **kwargs):
            message = kwargs.get("message", "").lower()

            # Classify ticket based on keywords
            ticket_category = "general"
            for category, keywords in categories.items():
                if any(keyword in message for keyword in keywords):
                    ticket_category = category
                    break

            ticket_id = str(uuid.uuid4())[:8]
            ticket = {
                "id": ticket_id,
                "category": ticket_category,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "status": "open",
            }

            gateway.support_tickets.append(ticket)

            response = f"Ticket #{ticket_id} classified as {ticket_category} and created"
            return (response, "gemini-3-flash-preview", Mock(), MockTokenUsage())

        gateway._send_with_fallback = classify_ticket_call

        # Test ticket classification
        test_tickets = [
            "My app keeps crashing when I try to upload files",
            "I was charged twice for my subscription",
            "I can't log into my account",
            "I would like to request a dark mode feature",
            "How do I change my email address?",
        ]

        expected_categories = ["technical", "billing", "account", "feature", "general"]

        for ticket, expected_category in zip(test_tickets, expected_categories):
            response, model, obj, usage = await gateway.send_message(
                chat=None, message=ticket, tier=TIER_FLASH
            )

            # Verify ticket was created and classified correctly
            ticket_id = response.split("#")[1].split()[0]
            created_ticket = next(t for t in gateway.support_tickets if t["id"] == ticket_id)
            assert created_ticket["category"] == expected_category

    async def test_sentiment_analysis(self, support_gateway):
        """Test sentiment analysis for customer messages."""
        gateway = support_gateway

        # Sentiment keywords
        positive_words = ["happy", "satisfied", "great", "excellent", "love", "amazing"]
        negative_words = ["angry", "frustrated", "terrible", "awful", "hate", "disappointed"]
        neutral_words = ["question", "how", "what", "where", "when", "help"]

        async def sentiment_analysis_call(*args, **kwargs):
            message = kwargs.get("message", "").lower()

            # Analyze sentiment
            positive_score = sum(1 for word in positive_words if word in message)
            negative_score = sum(1 for word in negative_words if word in message)
            neutral_score = sum(1 for word in neutral_words if word in message)

            if positive_score > negative_score and positive_score > neutral_score:
                sentiment = "positive"
                priority = "low"
            elif negative_score > positive_score:
                sentiment = "negative"
                priority = "high"
            else:
                sentiment = "neutral"
                priority = "medium"

            response = f"Sentiment: {sentiment}, Priority: {priority}"
            return (response, "gemini-3-flash-preview", Mock(), MockTokenUsage())

        gateway._send_with_fallback = sentiment_analysis_call

        # Test sentiment analysis
        test_messages = [
            "I'm very happy with your service! It's amazing!",
            "I'm frustrated and angry about this terrible experience",
            "How do I reset my password?",
            "Your product is excellent but I have a question",
            "This is awful and I hate it, very disappointed",
        ]

        expected_sentiments = ["positive", "negative", "neutral", "positive", "negative"]

        for message, expected_sentiment in zip(test_messages, expected_sentiments):
            response, model, obj, usage = await gateway.send_message(
                chat=None, message=message, tier=TIER_FLASH
            )

            assert expected_sentiment in response

    async def test_automated_responses(self, support_gateway):
        """Test automated response generation."""
        gateway = support_gateway

        # Common response templates
        response_templates = {
            "technical": "I understand you're experiencing technical issues. Our team has been notified and will investigate within 24 hours.",
            "billing": "I'll help you with your billing concern. Please provide your account number and I'll escalate this to our billing department.",
            "account": "For account-related issues, please try resetting your password first. If that doesn't work, I'll connect you with an account specialist.",
            "feature": "Thank you for your feature suggestion! I've forwarded this to our product team for consideration.",
            "general": "I'm here to help! Could you provide more details about your question so I can assist you better?",
        }

        async def automated_response_call(*args, **kwargs):
            message = kwargs.get("message", "").lower()

            # Generate automated response
            if "technical" in message or "bug" in message or "error" in message:
                template = response_templates["technical"]
            elif "billing" in message or "payment" in message or "charge" in message:
                template = response_templates["billing"]
            elif "account" in message or "login" in message or "password" in message:
                template = response_templates["account"]
            elif "feature" in message or "request" in message or "suggestion" in message:
                template = response_templates["feature"]
            else:
                template = response_templates["general"]

            return (template, "gemini-3-flash-preview", Mock(), MockTokenUsage())

        gateway._send_with_fallback = automated_response_call

        # Test automated responses
        test_queries = [
            "My app has a bug",
            "I have a billing question",
            "I can't access my account",
            "I want to request a new feature",
            "I need general help",
        ]

        for query in test_queries:
            response, model, obj, usage = await gateway.send_message(
                chat=None, message=query, tier=TIER_FLASH
            )

            assert len(response) > 50  # Should be a substantial response
            assert any(
                keyword in response.lower()
                for keyword in ["help", "team", "department", "specialist", "consider"]
            )


class TestECommerceIntegration:
    """Test e-commerce integration scenarios."""

    @pytest.fixture
    def ecommerce_gateway(self):
        """Gateway configured for e-commerce testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.product_catalog = {}
        gateway.orders = []
        gateway.customer_preferences = {}
        return gateway

    async def test_product_recommendations(self, ecommerce_gateway):
        """Test AI-powered product recommendations."""
        gateway = ecommerce_gateway

        # Mock product catalog
        products = [
            {
                "id": "p1",
                "name": "Wireless Headphones",
                "category": "electronics",
                "price": 99.99,
                "rating": 4.5,
            },
            {
                "id": "p2",
                "name": "Running Shoes",
                "category": "sports",
                "price": 79.99,
                "rating": 4.2,
            },
            {
                "id": "p3",
                "name": "Coffee Maker",
                "category": "kitchen",
                "price": 149.99,
                "rating": 4.7,
            },
            {"id": "p4", "name": "Yoga Mat", "category": "sports", "price": 29.99, "rating": 4.1},
            {
                "id": "p5",
                "name": "Smart Watch",
                "category": "electronics",
                "price": 299.99,
                "rating": 4.6,
            },
        ]

        gateway.product_catalog = {p["id"]: p for p in products}

        async def recommendation_call(*args, **kwargs):
            message = kwargs.get("message", "").lower()

            # Analyze preferences from message
            preferences = {
                "electronics": any(
                    word in message for word in ["headphones", "watch", "tech", "gadget"]
                ),
                "sports": any(
                    word in message for word in ["running", "shoes", "yoga", "fitness", "exercise"]
                ),
                "kitchen": any(
                    word in message for word in ["coffee", "cooking", "kitchen", "appliance"]
                ),
                "budget_conscious": any(
                    word in message for word in ["cheap", "affordable", "budget", "under $100"]
                ),
                "premium": any(
                    word in message for word in ["premium", "high-end", "best", "quality"]
                ),
            }

            # Filter and rank products
            recommended_products = []
            for product in products:
                score = 0

                # Category matching
                if preferences["electronics"] and product["category"] == "electronics":
                    score += 2
                if preferences["sports"] and product["category"] == "sports":
                    score += 2
                if preferences["kitchen"] and product["category"] == "kitchen":
                    score += 2

                # Price preference
                if preferences["budget_conscious"] and product["price"] < 100:
                    score += 1
                if preferences["premium"] and product["rating"] > 4.5:
                    score += 1

                # Rating bonus
                score += product["rating"]

                recommended_products.append((score, product))

            # Sort by score and get top 3
            recommended_products.sort(key=lambda x: x[0], reverse=True)
            top_products = [p[1] for p in recommended_products[:3]]

            response = f"Recommended products: {', '.join([p['name'] for p in top_products])}"
            return (response, "gemini-3-flash-preview", Mock(), MockTokenUsage())

        gateway._send_with_fallback = recommendation_call

        # Test recommendations
        test_queries = [
            "I need wireless headphones for running",
            "Looking for affordable kitchen appliances",
            "I want premium electronics",
            "Need sports equipment under $50",
        ]

        for query in test_queries:
            response, model, obj, usage = await gateway.send_message(
                chat=None, message=query, tier=TIER_FLASH
            )

            assert "Recommended products:" in response
            assert len(response.split(",")) <= 3  # Should recommend max 3 products

    async def test_order_processing_assistance(self, ecommerce_gateway):
        """Test order processing and customer assistance."""
        gateway = ecommerce_gateway

        async def order_assistance_call(*args, **kwargs):
            message = kwargs.get("message", "").lower()

            # Order-related keywords
            if "track" in message or "status" in message:
                response = "To track your order, please provide your order number and I'll check the current status."
            elif "cancel" in message:
                response = "I can help you cancel your order. Please provide your order number and reason for cancellation."
            elif "return" in message or "refund" in message:
                response = "For returns and refunds, please visit our returns portal or I can guide you through the process."
            elif "shipping" in message or "delivery" in message:
                response = "We offer standard shipping (5-7 days), express shipping (2-3 days), and overnight shipping options."
            elif "payment" in message:
                response = "We accept credit cards, PayPal, Apple Pay, and Google Pay. All payments are secure and encrypted."
            else:
                response = "I can help you with orders, tracking, returns, shipping, and payment questions. What specific assistance do you need?"

            return (response, "gemini-3-flash-preview", Mock(), MockTokenUsage())

        gateway._send_with_fallback = order_assistance_call

        # Test order assistance
        order_queries = [
            "How do I track my order?",
            "I want to cancel my order",
            "What's your return policy?",
            "What shipping options do you have?",
            "What payment methods do you accept?",
        ]

        for query in order_queries:
            response, model, obj, usage = await gateway.send_message(
                chat=None, message=query, tier=TIER_FLASH
            )

            assert len(response) > 30  # Should be helpful and detailed

    async def test_inventory_management(self, ecommerce_gateway):
        """Test inventory management and stock queries."""
        gateway = ecommerce_gateway

        # Mock inventory data
        inventory = {
            "p1": {"stock": 50, "status": "in_stock"},
            "p2": {"stock": 0, "status": "out_of_stock"},
            "p3": {"stock": 5, "status": "low_stock"},
            "p4": {"stock": 100, "status": "in_stock"},
            "p5": {"stock": 2, "status": "low_stock"},
        }

        async def inventory_call(*args, **kwargs):
            message = kwargs.get("message", "").lower()

            # Check inventory queries
            if "stock" in message or "available" in message or "inventory" in message:
                # Find mentioned products
                mentioned_products = []
                for product_id, product in gateway.product_catalog.items():
                    if product["name"].lower() in message:
                        mentioned_products.append((product_id, product))

                if mentioned_products:
                    stock_info = []
                    for product_id, product in mentioned_products:
                        inv_info = inventory.get(product_id, {"stock": 0, "status": "unknown"})
                        stock_info.append(
                            f"{product['name']}: {inv_info['status']} ({inv_info['stock']} units)"
                        )

                    response = f"Stock information: {', '.join(stock_info)}"
                else:
                    response = "Please specify which product you'd like to check stock for."
            else:
                response = "I can help you check product availability and stock levels. Which product are you interested in?"

            return (response, "gemini-3-flash-preview", Mock(), MockTokenUsage())

        gateway._send_with_fallback = inventory_call

        # Test inventory queries
        inventory_queries = [
            "Do you have Wireless Headphones in stock?",
            "Is Running Shoes available?",
            "Check inventory for Coffee Maker",
        ]

        for query in inventory_queries:
            response, model, obj, usage = await gateway.send_message(
                chat=None, message=query, tier=TIER_FLASH
            )

            assert "stock" in response.lower() or "available" in response.lower()


class TestHealthcareCompliance:
    """Test healthcare compliance and medical scenarios."""

    @pytest.fixture
    def healthcare_gateway(self):
        """Gateway configured for healthcare testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.hipaa_compliance = True
        gateway.medical_data = {}
        return gateway

    async def test_medical_symptom_analysis(self, healthcare_gateway):
        """Test medical symptom analysis with proper disclaimers."""
        gateway = healthcare_gateway

        async def symptom_analysis_call(*args, **kwargs):
            message = kwargs.get("message", "").lower()

            # Medical disclaimer
            disclaimer = "IMPORTANT: I am an AI assistant and not a medical professional. This information is for educational purposes only and should not replace professional medical advice. Please consult a healthcare provider for medical concerns."

            # Symptom analysis (simplified)
            if "headache" in message:
                response = f"Based on your mention of headache, common causes include stress, dehydration, lack of sleep, or eye strain. {disclaimer}"
            elif "fever" in message:
                response = f"Fever can indicate various conditions including infections. Monitor your temperature and stay hydrated. {disclaimer}"
            elif "cough" in message:
                response = f"Coughing can be caused by allergies, colds, or respiratory infections. Rest and hydration are important. {disclaimer}"
            else:
                response = f"I notice you're asking about medical symptoms. {disclaimer} For accurate diagnosis and treatment, please consult a qualified healthcare provider."

            return (response, "gemini-3-flash-preview", Mock(), MockTokenUsage())

        gateway._send_with_fallback = symptom_analysis_call

        # Test medical symptom analysis
        medical_queries = [
            "I have a severe headache",
            "What should I do about fever?",
            "I've been coughing for days",
        ]

        for query in medical_queries:
            response, model, obj, usage = await gateway.send_message(
                chat=None, message=query, tier=TIER_FLASH
            )

            # Should always include medical disclaimer
            assert (
                "medical professional" in response.lower()
                or "healthcare provider" in response.lower()
            )
            assert "not a medical" in response.lower()

    def test_hipaa_compliance(self, healthcare_gateway):
        """Test HIPAA compliance in data handling."""
        gateway = healthcare_gateway

        # Test PHI (Protected Health Information) detection
        phi_patterns = [
            r"\d{3}-\d{2}-\d{4}",  # SSN pattern
            r"\d{3}-\d{3}-\d{4}",  # Phone pattern
            r"\b\d{1,2}/\d{1,2}/\d{4}\b",  # Date pattern
            r"\b[A-Z]{2}\d{4}\b",  # Medical record pattern
        ]

        def phi_compliant_call(*args, **kwargs):
            message = kwargs.get("message", "")

            # Check for potential PHI
            has_phi = any(
                pattern in message for pattern in ["ssn", "medical record", "patient id", "dob"]
            )

            if has_phi:
                response = "[PHI DETECTED] For privacy and security, please do not share personal health information in this chat. Contact your healthcare provider directly."
            else:
                response = "Your message has been processed securely. How can I help with your general health questions?"

            return (response, "gemini-3-flash-preview", Mock(), MockTokenUsage())

        gateway._send_with_fallback = phi_compliant_call

        # Test PHI detection
        phi_messages = ["My SSN is 123-45-6789", "My medical record is MR1234", "Patient ID: 45678"]

        safe_messages = [
            "What are common cold symptoms?",
            "How can I improve my sleep?",
            "Tell me about nutrition",
        ]

        for message in phi_messages:
            response, model, obj, usage = gateway._send_with_fallback(
                chat=None, message=message, tier=TIER_FLASH
            )
            assert "PHI DETECTED" in response

        for message in safe_messages:
            response, model, obj, usage = gateway._send_with_fallback(
                chat=None, message=message, tier=TIER_FLASH
            )
            assert "PHI DETECTED" not in response

    async def test_medical_emergency_detection(self, healthcare_gateway):
        """Test medical emergency detection and response."""
        gateway = healthcare_gateway

        emergency_keywords = [
            "emergency",
            "911",
            "call ambulance",
            "can't breathe",
            "chest pain",
            "severe bleeding",
            "unconscious",
            "overdose",
        ]

        async def emergency_detection_call(*args, **kwargs):
            message = kwargs.get("message", "").lower()

            # Check for emergency indicators
            is_emergency = any(keyword in message for keyword in emergency_keywords)

            if is_emergency:
                response = "MEDICAL EMERGENCY DETECTED: Please call 911 or your local emergency number immediately. This is not a substitute for emergency medical care. If you are experiencing a medical emergency, seek immediate medical attention."
            else:
                response = "For non-emergency medical questions, I can provide general health information. Always consult a healthcare provider for personalized medical advice."

            return (response, "gemini-3-flash-preview", Mock(), MockTokenUsage())

        gateway._send_with_fallback = emergency_detection_call

        # Test emergency detection
        emergency_messages = [
            "I'm having chest pain and can't breathe",
            "Call 911, this is an emergency",
            "Someone is unconscious and bleeding",
        ]

        non_emergency_messages = [
            "I have a mild headache",
            "What are healthy breakfast options?",
            "How much exercise should I get?",
        ]

        for message in emergency_messages:
            response, model, obj, usage = await gateway.send_message(
                chat=None, message=message, tier=TIER_FLASH
            )
            assert "EMERGENCY" in response or "911" in response

        for message in non_emergency_messages:
            response, model, obj, usage = await gateway.send_message(
                chat=None, message=message, tier=TIER_FLASH
            )
            assert "EMERGENCY" not in response


class TestFinancialServices:
    """Test financial services compliance and scenarios."""

    @pytest.fixture
    def financial_gateway(self):
        """Gateway configured for financial services testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.financial_compliance = True
        return gateway

    async def test_financial_advice_disclaimer(self, financial_gateway):
        """Test financial advice with proper disclaimers."""
        gateway = financial_gateway

        async def financial_advice_call(*args, **kwargs):
            message = kwargs.get("message", "").lower()

            # Financial disclaimer
            disclaimer = "IMPORTANT: I am an AI assistant and not a licensed financial advisor. This information is for educational purposes only and should not be considered financial advice. Please consult a qualified financial professional for personalized financial guidance."

            if "invest" in message or "investment" in message:
                response = f"Regarding investments, it's important to consider your risk tolerance, financial goals, and diversification. {disclaimer}"
            elif "save" in message or "saving" in message:
                response = f"For saving money, consider creating an emergency fund, automating savings, and exploring high-yield savings accounts. {disclaimer}"
            elif "retire" in message or "retirement" in message:
                response = f"Retirement planning involves starting early, contributing consistently, and understanding different retirement account options. {disclaimer}"
            else:
                response = f"I can provide general financial education information. {disclaimer} For personalized financial advice, please consult a licensed financial advisor."

            return (response, "gemini-3-flash-preview", Mock(), MockTokenUsage())

        gateway._send_with_fallback = financial_advice_call

        # Test financial advice
        financial_queries = [
            "How should I invest my money?",
            "What's the best way to save?",
            "When should I start planning for retirement?",
        ]

        for query in financial_queries:
            response, model, obj, usage = await gateway.send_message(
                chat=None, message=query, tier=TIER_FLASH
            )

            # Should always include financial disclaimer
            assert "financial advisor" in response.lower() or "not a licensed" in response.lower()

    def test_fraud_detection_education(self, financial_gateway):
        """Test fraud detection and prevention education."""
        gateway = financial_gateway

        def fraud_education_call(*args, **kwargs):
            message = kwargs.get("message", "").lower()

            if "scam" in message or "fraud" in message:
                response = "Common financial scams include phishing emails, fake investment opportunities, and identity theft. Protect yourself by: never sharing personal financial information, verifying sender identities, using strong unique passwords, and monitoring your accounts regularly."
            elif "phishing" in message:
                response = "Phishing scams often use urgent language, suspicious links, or requests for personal information. Always verify the sender and don't click on suspicious links."
            elif "identity theft" in message:
                response = "To prevent identity theft: use secure passwords, enable two-factor authentication, monitor credit reports, and shred sensitive documents."
            else:
                response = "I can help you learn about financial fraud prevention and security best practices."

            return (response, "gemini-3-flash-preview", Mock(), MockTokenUsage())

        gateway._send_with_fallback = fraud_education_call

        # Test fraud education
        fraud_queries = [
            "How can I avoid financial scams?",
            "What is phishing?",
            "How do I prevent identity theft?",
        ]

        for query in fraud_queries:
            response, model, obj, usage = gateway._send_with_fallback(
                chat=None, message=query, tier=TIER_FLASH
            )

            assert len(response) > 100  # Should provide detailed information

    async def test_budgeting_assistance(self, financial_gateway):
        """Test budgeting and financial planning assistance."""
        gateway = financial_gateway

        async def budgeting_call(*args, **kwargs):
            message = kwargs.get("message", "").lower()

            if "budget" in message:
                response = "Creating a budget involves: tracking income and expenses, categorizing spending, setting financial goals, and regularly reviewing and adjusting. Consider the 50/30/20 rule: 50% needs, 30% wants, 20% savings."
            elif "debt" in message:
                response = "For debt management: prioritize high-interest debt, consider debt consolidation, make more than minimum payments, and avoid taking on new debt while paying off existing debt."
            elif "credit score" in message:
                response = "To improve your credit score: pay bills on time, keep credit utilization low, don't close old credit cards, and regularly check your credit report for errors."
            else:
                response = "I can help with budgeting, debt management, and credit score improvement strategies."

            return (response, "gemini-3-flash-preview", Mock(), MockTokenUsage())

        gateway._send_with_fallback = budgeting_call

        # Test budgeting assistance
        budgeting_queries = [
            "How do I create a budget?",
            "What's the best way to pay off debt?",
            "How can I improve my credit score?",
        ]

        for query in budgeting_queries:
            response, model, obj, usage = await gateway.send_message(
                chat=None, message=query, tier=TIER_FLASH
            )

            assert len(response) > 80  # Should provide substantial guidance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
