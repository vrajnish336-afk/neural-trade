import logging
import streamlit as st
from collections import deque
from typing import List
from datetime import datetime

class StreamlitLogHandler(logging.Handler):
    def __init__(self, capacity: int = 100):
        super().__init__()
        self.capacity = capacity
        # We need a place to store logs. Streamlit re-runs script, 
        # so we attach it to st.session_state if available.
        # But Handler persists across runs if attached to root logger.
        self.log_queue = deque(maxlen=capacity)
        
    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.append((record.levelname, record.name, record.getMessage(), msg))
        except Exception:
            self.handleError(record)
            
    def get_logs(self) -> List[tuple]:
        return list(self.log_queue)

# Global singleton handler for Streamlit
_streamlit_handler = None

def init_streamlit_logger():
    global _streamlit_handler
    if _streamlit_handler is None:
        _streamlit_handler = StreamlitLogHandler(capacity=200)
        from app.logging_config import CustomFormatter
        _streamlit_handler.setFormatter(CustomFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
        _streamlit_handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(_streamlit_handler)
    return _streamlit_handler

def render_logs_tab():
    st.markdown("### SYSTEM TERMINAL LOGS")
    
    handler = init_streamlit_logger()
    
    cols = st.columns([2, 2, 8])
    with cols[0]:
        level_filter = st.selectbox("Level", ["ALL", "INFO", "SUCCESS", "WARNING", "ERROR"])
    with cols[1]:
        module_filter = st.text_input("Module", value="")
        
    logs = handler.get_logs()
    
    filtered_logs = []
    for level, module, raw_msg, formatted_msg in logs:
        if level_filter != "ALL" and level != level_filter:
            continue
        if module_filter and module_filter.lower() not in module.lower():
            continue
        filtered_logs.append((level, formatted_msg))
        
    log_html = ""
    for level, msg in filtered_logs:
        color_class = "log-info"
        if level == "SUCCESS": color_class = "log-success"
        elif level == "WARNING": color_class = "log-warning"
        elif level == "ERROR": color_class = "log-error"
        
        log_html += f'<div class="{color_class}">{msg}</div>'
        
    if not log_html:
        log_html = '<div style="color: #8b949e;">No logs match the current filters.</div>'
        
    st.markdown(f'<div class="log-panel">{log_html}</div>', unsafe_allow_html=True)
