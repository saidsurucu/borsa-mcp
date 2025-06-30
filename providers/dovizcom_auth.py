"""
Dovizcom Authentication Manager
This module handles dynamic token extraction and management for Doviz.com API.
"""
import httpx
import logging
import time
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class DovizcomAuthManager:
    """Manages authentication tokens for Doviz.com API with automatic refresh."""
    
    TOKEN_EXPIRY_SECONDS = 3600  # 1 hour
    FALLBACK_TOKENS = {
        'calendar': 'd00c1214cbca6a7a1b4728a8cc78cd69ba99e0d2ddb6d0687d2ed34f6a547b48',
        'assets': '3e75d7fabf1c50c8b962626dd0e5ea22d8000815e1b0920d0a26afd77fcd6609'
    }
    
    def __init__(self, client: httpx.AsyncClient):
        self._http_client = client
        self._current_token: Optional[str] = None
        self._token_expiry: Optional[float] = None
        self._last_extraction_attempt: Optional[float] = None
        self._extraction_failures = 0
        
    async def get_valid_token(self, service_type: str = 'assets') -> str:
        """
        Get a valid Bearer token for API requests.
        
        Args:
            service_type: 'assets' or 'calendar' for different fallback tokens
            
        Returns:
            Valid Bearer token string
        """
        # Check if current token is still valid
        if self._is_token_valid():
            return self._current_token
            
        # Try to refresh token
        if await self._should_attempt_refresh():
            try:
                new_token = await self._extract_token_from_website()
                if new_token:
                    self._current_token = new_token
                    self._token_expiry = time.time() + self.TOKEN_EXPIRY_SECONDS
                    self._extraction_failures = 0
                    logger.info("Successfully extracted fresh token from doviz.com")
                    return new_token
                else:
                    self._extraction_failures += 1
                    logger.warning(f"Token extraction failed (attempt {self._extraction_failures})")
            except Exception as e:
                self._extraction_failures += 1
                logger.error(f"Error during token extraction: {e}")
                
            self._last_extraction_attempt = time.time()
        
        # Fall back to known working token
        fallback_token = self.FALLBACK_TOKENS.get(service_type, self.FALLBACK_TOKENS['assets'])
        logger.info(f"Using fallback token for {service_type}")
        return fallback_token
        
    async def refresh_token_on_401(self, service_type: str = 'assets') -> str:
        """
        Force token refresh when getting 401 errors.
        
        Args:
            service_type: 'assets' or 'calendar' for different fallback tokens
            
        Returns:
            New Bearer token string
        """
        logger.warning("Received 401 error, forcing token refresh")
        self._current_token = None  # Invalidate current token
        return await self.get_valid_token(service_type)
        
    def _is_token_valid(self) -> bool:
        """Check if current token is still valid."""
        return (self._current_token is not None and 
                self._token_expiry is not None and 
                time.time() < self._token_expiry)
                
    async def _should_attempt_refresh(self) -> bool:
        """Check if we should attempt token extraction."""
        # Don't attempt too frequently to avoid being blocked
        if self._last_extraction_attempt:
            time_since_last = time.time() - self._last_extraction_attempt
            if time_since_last < 300:  # 5 minutes cooldown
                return False
                
        # Stop trying after too many failures
        if self._extraction_failures >= 3:
            return False
            
        return True
        
    async def _extract_token_from_website(self) -> Optional[str]:
        """
        Extract Bearer token from doviz.com website.
        
        Returns:
            Extracted token string or None if extraction failed
        """
        try:
            # Get main page with realistic headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none'
            }
            
            response = await self._http_client.get(
                "https://www.doviz.com/", 
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            
            html_content = response.text
            
            # Method 1: Look for token in script tags
            token = await self._extract_from_scripts(html_content)
            if token:
                return token
                
            # Method 2: Look for token in inline JSON/config
            token = await self._extract_from_inline_config(html_content)
            if token:
                return token
                
            # Method 3: Look for token in window variables
            token = await self._extract_from_window_vars(html_content)
            if token:
                return token
                
            logger.warning("No token found in website content")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting token from website: {e}")
            return None
            
    async def _extract_from_scripts(self, html_content: str) -> Optional[str]:
        """Extract token from script tags."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            scripts = soup.find_all('script')
            
            # Token patterns to look for
            token_patterns = [
                r'token["\']?\s*:\s*["\']([a-f0-9]{64})["\']',
                r'apiKey["\']?\s*:\s*["\']([a-f0-9]{64})["\']',
                r'bearer["\']?\s*:\s*["\']([a-f0-9]{64})["\']',
                r'authorization["\']?\s*:\s*["\']Bearer\s+([a-f0-9]{64})["\']',
                r'AUTH_TOKEN["\']?\s*:\s*["\']([a-f0-9]{64})["\']',
                r'API_TOKEN["\']?\s*:\s*["\']([a-f0-9]{64})["\']',
                r'token["\']?\s*:\s*["\']([a-f0-9]{64})["\']',
                r'([a-f0-9]{64})'  # Any 64-char hex string as fallback
            ]
            
            for script in scripts:
                if script.string:
                    for pattern in token_patterns:
                        match = re.search(pattern, script.string, re.IGNORECASE)
                        if match:
                            token = match.group(1)
                            logger.info(f"Found token in script tag: {token[:16]}...")
                            return token
                            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting from scripts: {e}")
            return None
            
    async def _extract_from_inline_config(self, html_content: str) -> Optional[str]:
        """Extract token from inline configuration objects."""
        try:
            # Look for common config patterns
            config_patterns = [
                r'window\.__INITIAL_STATE__.*?token.*?["\']([a-f0-9]{64})["\']',
                r'window\.APP_CONFIG.*?token.*?["\']([a-f0-9]{64})["\']',
                r'window\.CONFIG.*?token.*?["\']([a-f0-9]{64})["\']',
                r'data-token=["\']([a-f0-9]{64})["\']',
                r'token["\']?\s*:\s*["\']([a-f0-9]{64})["\']'
            ]
            
            for pattern in config_patterns:
                match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
                if match:
                    token = match.group(1)
                    logger.info(f"Found token in config: {token[:16]}...")
                    return token
                    
            return None
            
        except Exception as e:
            logger.error(f"Error extracting from config: {e}")
            return None
            
    async def _extract_from_window_vars(self, html_content: str) -> Optional[str]:
        """Extract token from window variables."""
        try:
            # Look for window variable assignments
            window_patterns = [
                r'window\.token\s*=\s*["\']([a-f0-9]{64})["\']',
                r'window\.apiToken\s*=\s*["\']([a-f0-9]{64})["\']',
                r'window\.authToken\s*=\s*["\']([a-f0-9]{64})["\']',
                r'var\s+token\s*=\s*["\']([a-f0-9]{64})["\']',
                r'const\s+token\s*=\s*["\']([a-f0-9]{64})["\']',
                r'let\s+token\s*=\s*["\']([a-f0-9]{64})["\']'
            ]
            
            for pattern in window_patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    token = match.group(1)
                    logger.info(f"Found token in window var: {token[:16]}...")
                    return token
                    
            return None
            
        except Exception as e:
            logger.error(f"Error extracting from window vars: {e}")
            return None