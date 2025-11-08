"""
OpenAI Service
Centralized service for all OpenAI API interactions with error handling,
cost calculation, and token counting. Includes a mock path for local
development environments where the OpenAI SDK or API key may be absent.
"""

import json
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:  # pragma: no cover - handled via mock mode
    OPENAI_AVAILABLE = False
    OpenAI = None


class OpenAIServiceError(Exception):
    """Raised when OpenAI service encounters an error"""
    pass


class OpenAIService:
    """Centralized OpenAI API service"""

    # Model selection for different tasks
    MODELS = {
        'cheap': 'gpt-4o-mini',  # $0.00015 input, $0.0006 output per 1K tokens
        'standard': 'gpt-3.5-turbo',  # $0.0005 input, $0.0015 output per 1K tokens
        'advanced': 'gpt-4-turbo',  # $0.01 input, $0.03 output per 1K tokens
    }

    # Feature to model mapping (cost optimization)
    FEATURE_MODELS = {
        'product_description': 'cheap',
        'report_narrative': 'cheap',
        'customer_insight': 'cheap',
        'collection_message': 'cheap',
        'natural_language_query': 'cheap',
        'payment_prediction': 'cheap',
        'credit_assessment': 'advanced',  # Complex analysis
        'collection_priority': 'advanced',
        'portfolio_dashboard': 'advanced',
        'inventory_forecast': 'advanced',
    }

    # Pricing per 1K tokens in USD
    MODEL_PRICING = {
        'gpt-4o-mini': {'input': 0.00015, 'output': 0.0006},
        'gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
        'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
    }

    # USD to GHS exchange rate (update periodically)
    USD_TO_GHS = Decimal('16.00')  # Approximate rate

    def __init__(self) -> None:
        """Initialize OpenAI client or configure mock behaviour."""

        configured_mock = getattr(settings, 'OPENAI_USE_MOCK', False)
        api_key = getattr(settings, 'OPENAI_API_KEY', None)

        if configured_mock:
            self.mock_mode = True
        elif not OPENAI_AVAILABLE:
            self.mock_mode = True
        else:
            self.mock_mode = False

        if self.mock_mode:
            if not OPENAI_AVAILABLE and not configured_mock:
                raise ImportError(
                    "OpenAI package not installed. Run: pip install openai or set OPENAI_USE_MOCK=true"
                )
            self.client = None
            self._mock_model = 'mock-local'
            return

        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured in settings")

        try:
            self.client = OpenAI(api_key=api_key, timeout=60.0, max_retries=2)
        except TypeError:
            # Fallback for older SDK signatures
            self.client = OpenAI(api_key=api_key)
        self._mock_model = 'openai'
    
    def _get_model_for_feature(self, feature: str) -> str:
        """Get the appropriate model for a feature"""
        model_tier = self.FEATURE_MODELS.get(feature, 'cheap')
        return self.MODELS[model_tier]
    
    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
        """Calculate cost in GHS for API call"""
        pricing = self.MODEL_PRICING.get(model, self.MODEL_PRICING['gpt-4o-mini'])
        
        # Cost in USD
        input_cost = (prompt_tokens / 1000) * pricing['input']
        output_cost = (completion_tokens / 1000) * pricing['output']
        total_usd = input_cost + output_cost
        
        # Convert to GHS
        total_ghs = Decimal(str(total_usd)) * self.USD_TO_GHS
        
        return total_ghs
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        feature: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        cache_key: Optional[str] = None,
        cache_ttl: int = 0
    ) -> Dict[str, Any]:
        """
        Make a chat completion request to OpenAI
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            feature: Feature name for model selection
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            json_mode: Force JSON output
            cache_key: Optional cache key for caching results
            cache_ttl: Cache time-to-live in seconds
        
        Returns:
            Dict with 'content', 'tokens', 'cost', 'processing_time_ms'
        """
        if self.mock_mode:
            return self._mock_chat_completion(messages, feature, cache_key, cache_ttl, json_mode)

        start_time = time.time()

        if cache_key and cache_ttl > 0:
            cached = cache.get(cache_key)
            if cached:
                return json.loads(cached)

        model = self._get_model_for_feature(feature)

        request_kwargs = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
        }

        if max_tokens:
            request_kwargs['max_tokens'] = max_tokens

        if json_mode:
            request_kwargs['response_format'] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**request_kwargs)

            content = response.choices[0].message.content
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            cost_ghs = self._calculate_cost(model, prompt_tokens, completion_tokens)
            processing_time_ms = int((time.time() - start_time) * 1000)

            result = {
                'content': content,
                'tokens': {
                    'prompt': prompt_tokens,
                    'completion': completion_tokens,
                    'total': total_tokens
                },
                'cost_ghs': float(cost_ghs),
                'processing_time_ms': processing_time_ms,
                'model': model
            }

            if cache_key and cache_ttl > 0:
                cache.set(cache_key, json.dumps(result), cache_ttl)

            return result

        except Exception as exc:  # pragma: no cover - network errors
            processing_time_ms = int((time.time() - start_time) * 1000)
            raise OpenAIServiceError(f"OpenAI API Error: {str(exc)}")
    
    def generate_text(
        self,
        prompt: str,
        system_prompt: str,
        feature: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Simple text generation helper
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            feature: Feature name
            **kwargs: Additional arguments for chat_completion
        
        Returns:
            Same as chat_completion
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        return self.chat_completion(messages=messages, feature=feature, **kwargs)
    
    def generate_json(
        self,
        prompt: str,
        system_prompt: str,
        feature: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate JSON response from OpenAI
        
        Returns:
            Dict with 'data' (parsed JSON), 'tokens', 'cost', 'processing_time_ms'
        """
        # Force JSON mode
        kwargs['json_mode'] = True
        
        # Add JSON instruction to system prompt
        if "JSON" not in system_prompt:
            system_prompt += "\n\nYou must respond with valid JSON only."
        
        result = self.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            feature=feature,
            **kwargs
        )
        
        # Parse JSON response
        try:
            result['data'] = json.loads(result['content'])
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from text
            import re
            json_match = re.search(r'\{.*\}', result['content'], re.DOTALL)
            if json_match:
                result['data'] = json.loads(json_match.group())
            else:
                raise ValueError("OpenAI did not return valid JSON")
        
        return result

    # ------------------------------------------------------------------
    # Mock helpers (development fallback)
    # ------------------------------------------------------------------

    def _mock_chat_completion(
        self,
        messages: List[Dict[str, str]],
        feature: str,
        cache_key: Optional[str],
        cache_ttl: int,
        json_mode: bool
    ) -> Dict[str, Any]:
        start_time = time.time()
        system_prompt = messages[0]['content'] if messages else ""
        user_prompt = messages[-1]['content'] if messages else ""

        content = self._mock_content(system_prompt, user_prompt, feature, json_mode)

        prompt_tokens = sum(len(msg['content'].split()) for msg in messages)
        completion_tokens = len(content.split()) if not json_mode else len(content)
        total_tokens = prompt_tokens + completion_tokens
        processing_time_ms = int((time.time() - start_time) * 1000)

        result = {
            'content': content,
            'tokens': {
                'prompt': prompt_tokens,
                'completion': completion_tokens,
                'total': total_tokens
            },
            'cost_ghs': 0.0,
            'processing_time_ms': processing_time_ms,
            'model': self._mock_model
        }

        if cache_key and cache_ttl > 0:
            cache.set(cache_key, json.dumps(result), cache_ttl)

        return result

    def _mock_content(self, system_prompt: str, user_prompt: str, feature: str, json_mode: bool) -> str:
        lowered_system = system_prompt.lower()
        lowered_user = user_prompt.lower()

        if 'classify the following query' in lowered_system:
            return self._mock_classify(lowered_user)

        if 'extract relevant parameters' in lowered_system and json_mode:
            return json.dumps(self._mock_parameters(lowered_user))

        if 'please provide a comprehensive answer' in lowered_system:
            return self._mock_answer(user_prompt)

        if json_mode:
            return json.dumps({'mock': True})

        return "Local mock response generated without OpenAI access."

    def _mock_classify(self, query: str) -> str:
        query = query.lower()
        if any(keyword in query for keyword in ['inventory', 'stock', 'out of stock']):
            return 'inventory'
        if any(keyword in query for keyword in ['customer', 'client']):
            return 'customer'
        if any(keyword in query for keyword in ['profit', 'revenue', 'income', 'margin']):
            return 'financial'
        if any(keyword in query for keyword in ['product', 'sell', 'sales', 'best selling']):
            return 'product'
        return 'sales'

    def _mock_parameters(self, query: str) -> Dict[str, Any]:
        import re

        query_lower = query.lower()
        params: Dict[str, Any] = {
            'date_start': None,
            'date_end': None,
            'product_name': None,
            'customer_name': None,
            'category': None,
            'limit': None,
            'time_period': None
        }

        if 'today' in query_lower:
            params['time_period'] = 'today'
        elif 'yesterday' in query_lower:
            params['time_period'] = 'yesterday'
        elif 'this week' in query_lower:
            params['time_period'] = 'this_week'
        elif 'this month' in query_lower:
            params['time_period'] = 'this_month'
        elif 'last month' in query_lower:
            params['time_period'] = 'last_month'
        elif 'this year' in query_lower:
            params['time_period'] = 'this_year'

        match = re.search(r'top\s+(\d+)', query_lower)
        if match:
            params['limit'] = int(match.group(1))

        product_match = re.search(r'(?:sales\s+of|sell\s+of|for)\s+(?P<name>[a-z0-9\s-]{3,})', query_lower)
        if product_match:
            candidate = product_match.group('name').strip()
            params['product_name'] = candidate.title()

        customer_match = re.search(r'customer\s+(?P<name>[a-z0-9\s-]{3,})', query_lower)
        if customer_match:
            params['customer_name'] = customer_match.group('name').strip().title()

        return params

    def _mock_answer(self, prompt: str) -> str:
        question = None
        data_json: Dict[str, Any] = {}

        if 'User Question:' in prompt:
            question_line = next(
                (line for line in prompt.splitlines() if line.startswith('User Question:')),
                None
            )
            if question_line:
                question = question_line.replace('User Question:', '').strip()

        if 'Data Retrieved:' in prompt:
            _, remainder = prompt.split('Data Retrieved:', 1)
            data_block = remainder
            if '\n\nPlease provide' in data_block:
                data_block, _ = data_block.split('\n\nPlease provide', 1)
            data_block = data_block.strip()
            try:
                data_json = json.loads(data_block)
            except json.JSONDecodeError:
                data_json = {}

        lines = ["Mock summary generated in offline mode."]
        if question:
            lines.append(f"Question: {question}")

        if isinstance(data_json, dict) and data_json:
            total_revenue = data_json.get('total_revenue')
            if total_revenue is not None:
                try:
                    lines.append(f"Reported revenue: GHS {float(total_revenue):,.2f}")
                except (TypeError, ValueError):
                    lines.append(f"Reported revenue: {total_revenue}")

            total_sales = data_json.get('total_sales')
            if total_sales is not None:
                lines.append(f"Total sales entries: {total_sales}")
            products = data_json.get('products')
            if isinstance(products, list) and products:
                top_product = products[0]
                name = top_product.get('product__name') or top_product.get('name') or 'Top product'
                quantity = top_product.get('total_quantity') or top_product.get('quantity')
                if quantity is not None:
                    lines.append(f"Top product suggestion: {name} with {quantity} units sold.")
                else:
                    lines.append(f"Top product suggestion: {name}.")
        else:
            lines.append("No structured data available for detailed summary.")

        lines.append("(Running with OPENAI_USE_MOCK enabled – connect to OpenAI for production-quality insights.)")

        return "\n".join(lines)


# Singleton instance
_openai_service = None

def get_openai_service() -> OpenAIService:
    """Get or create OpenAI service singleton"""
    global _openai_service
    if _openai_service is None:
        _openai_service = OpenAIService()
    return _openai_service
