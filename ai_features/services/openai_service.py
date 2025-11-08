"""
OpenAI Service
Centralized service for all OpenAI API interactions with error handling,
cost calculation, and token counting.
"""

import time
from typing import Dict, List, Optional, Any
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
import json

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None


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
    
    def __init__(self):
        """Initialize OpenAI client"""
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI package not installed. Run: pip install openai")
        
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured in settings")
        
        # Initialize OpenAI client with explicit parameters only
        try:
            self.client = OpenAI(
                api_key=api_key,
                timeout=60.0,
                max_retries=2
            )
        except TypeError as e:
            # Fallback for version compatibility
            self.client = OpenAI(api_key=api_key)
    
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
        start_time = time.time()
        
        # Check cache first
        if cache_key and cache_ttl > 0:
            cached = cache.get(cache_key)
            if cached:
                return json.loads(cached)
        
        # Select model
        model = self._get_model_for_feature(feature)
        
        # Prepare request kwargs
        request_kwargs = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
        }
        
        if max_tokens:
            request_kwargs['max_tokens'] = max_tokens
        
        if json_mode:
            request_kwargs['response_format'] = {"type": "json_object"}
        
        # Make API call
        try:
            response = self.client.chat.completions.create(**request_kwargs)
            
            # Extract data
            content = response.choices[0].message.content
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            
            # Calculate cost
            cost_ghs = self._calculate_cost(model, prompt_tokens, completion_tokens)
            
            # Calculate processing time
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
            
            # Cache if requested
            if cache_key and cache_ttl > 0:
                cache.set(cache_key, json.dumps(result), cache_ttl)
            
            return result
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            raise Exception(f"OpenAI API Error: {str(e)}")
    
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


# Singleton instance
_openai_service = None

def get_openai_service() -> OpenAIService:
    """Get or create OpenAI service singleton"""
    global _openai_service
    if _openai_service is None:
        _openai_service = OpenAIService()
    return _openai_service
