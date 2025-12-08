"""
Webhook client utilities for making HTTP requests to external services
"""
import httpx
import logging
from typing import Dict, Any, Optional
from app.core.config import HTTP_SUCCESS_MIN, HTTP_SUCCESS_MAX, HTTP_TIMEOUT_SECONDS, RESPONSE_TEXT_MAX_LENGTH
from app.core.constants import get_webhook_status, get_webhook_error_status

logger = logging.getLogger(__name__)


class WebhookClient:
    """Client for making webhook calls to external services"""
    
    def __init__(self, timeout: float = HTTP_TIMEOUT_SECONDS):
        """
        Initialize webhook client
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
    
    async def call_webhook(
        self,
        url: str,
        payload: Dict[str, Any],
        webhook_name: str = "webhook"
    ) -> tuple[bool, int, Optional[str]]:
        """
        Make a POST request to a webhook
        
        Args:
            url: Webhook URL
            payload: Request payload as dictionary
            webhook_name: Name of webhook for logging purposes
            
        Returns:
            Tuple of (success: bool, status_code: int, response_text: Optional[str])
        """
        logger.info(f"[{webhook_name.upper()}] Calling webhook: {url}")
        logger.debug(f"[{webhook_name.upper()}] Payload: {payload}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                status_code = response.status_code
                status_text = response.text[:RESPONSE_TEXT_MAX_LENGTH] if response.text else None
                
                logger.info(
                    f"[{webhook_name.upper()}] Response: status_code={status_code}, "
                    f"response_text={status_text}"
                )
                
                is_success = HTTP_SUCCESS_MIN <= status_code <= HTTP_SUCCESS_MAX
                return is_success, status_code, status_text
                
        except httpx.TimeoutException as e:
            error_msg = f"Webhook timeout: {str(e)}"
            logger.error(f"[{webhook_name.upper()}] {error_msg}")
            return False, 0, error_msg
            
        except httpx.RequestError as e:
            error_msg = f"Webhook request error: {str(e)}"
            logger.error(f"[{webhook_name.upper()}] {error_msg}")
            return False, 0, error_msg
            
        except Exception as e:
            error_msg = f"Webhook unexpected error: {str(e)}"
            logger.error(f"[{webhook_name.upper()}] {error_msg}", exc_info=True)
            return False, 0, error_msg
    
    async def call_webhook_with_success_field(
        self,
        url: str,
        payload: Dict[str, Any],
        webhook_name: str = "webhook"
    ) -> tuple[bool, int, Optional[str]]:
        """
        Make a POST request to a webhook and check for 'success' field in response
        
        Args:
            url: Webhook URL
            payload: Request payload as dictionary
            webhook_name: Name of webhook for logging purposes
            
        Returns:
            Tuple of (success: bool, status_code: int, response_text: Optional[str])
            Success is determined by 'success' field in JSON response (boolean or string "true"/"false")
            Falls back to HTTP status code if 'success' field is not available
        """
        logger.info(f"[{webhook_name.upper()}] Calling webhook: {url}")
        logger.debug(f"[{webhook_name.upper()}] Payload: {payload}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                status_code = response.status_code
                status_text = response.text[:RESPONSE_TEXT_MAX_LENGTH] if response.text else None
                
                logger.info(
                    f"[{webhook_name.upper()}] Response: status_code={status_code}, "
                    f"response_text={status_text}"
                )
                
                # Try to parse JSON and check 'success' field
                try:
                    response_json = response.json()
                    logger.debug(f"[{webhook_name.upper()}] Parsed JSON: {response_json}")
                    
                    success_value = response_json.get("success", False)
                    
                    # Convert string "true"/"false" to boolean
                    if isinstance(success_value, str):
                        success_value_lower = success_value.lower().strip()
                        if success_value_lower == "true":
                            success_value = True
                            logger.debug(f"[{webhook_name.upper()}] Converted 'true' string to boolean True")
                        elif success_value_lower == "false":
                            success_value = False
                            logger.debug(f"[{webhook_name.upper()}] Converted 'false' string to boolean False")
                        else:
                            # Unexpected string value, fallback to status code
                            logger.warning(
                                f"[{webhook_name.upper()}] Unexpected success string value '{success_value}', "
                                f"using status code as fallback"
                            )
                            return (
                                HTTP_SUCCESS_MIN <= status_code <= HTTP_SUCCESS_MAX,
                                status_code,
                                status_text
                            )
                    
                    if isinstance(success_value, bool):
                        logger.info(
                            f"[{webhook_name.upper()}] Success field: {success_value}"
                        )
                        return success_value, status_code, status_text
                    else:
                        # Not boolean or string, fallback to status code
                        logger.warning(
                            f"[{webhook_name.upper()}] Success field is not boolean or string "
                            f"(type: {type(success_value).__name__}), using status code as fallback"
                        )
                        return (
                            HTTP_SUCCESS_MIN <= status_code <= HTTP_SUCCESS_MAX,
                            status_code,
                            status_text
                        )
                        
                except (ValueError, KeyError) as e:
                    # Cannot parse JSON or no 'success' field, fallback to status code
                    logger.warning(
                        f"[{webhook_name.upper()}] Could not parse JSON or find 'success' field: {str(e)}. "
                        f"Using status code as fallback"
                    )
                    return (
                        HTTP_SUCCESS_MIN <= status_code <= HTTP_SUCCESS_MAX,
                        status_code,
                        status_text
                    )
                
        except httpx.TimeoutException as e:
            error_msg = f"Webhook timeout: {str(e)}"
            logger.error(f"[{webhook_name.upper()}] {error_msg}")
            return False, 0, error_msg
            
        except httpx.RequestError as e:
            error_msg = f"Webhook request error: {str(e)}"
            logger.error(f"[{webhook_name.upper()}] {error_msg}")
            return False, 0, error_msg
            
        except Exception as e:
            error_msg = f"Webhook unexpected error: {str(e)}"
            logger.error(f"[{webhook_name.upper()}] {error_msg}", exc_info=True)
            return False, 0, error_msg


# Global webhook client instance
webhook_client = WebhookClient()

