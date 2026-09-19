import logging
import io
import sys
from app.logging_config import setup_logging, SUCCESS_LEVEL

def test_success_logging_level():
    # Setup our custom logging
    setup_logging(log_level="DEBUG")
    
    logger = logging.getLogger("test_success")
    
    # Capture output
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    from app.logging_config import CustomFormatter
    handler.setFormatter(CustomFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    
    # Check SUCCESS_LEVEL is defined and available
    assert SUCCESS_LEVEL == 25
    assert hasattr(logger, "success")
    
    # Emit a success message
    logger.success("Signal analysis completed successfully")
    
    log_output = log_capture.getvalue()
    
    assert "SUCCESS" in log_output
    assert "Signal analysis completed successfully" in log_output
    assert "test_success" in log_output
