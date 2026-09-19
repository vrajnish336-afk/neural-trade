import hashlib
import json
from typing import Dict, Any

class FingerprintGenerator:
    
    SENSITIVE_KEYS = {"api_key", "secret", "password", "token", "credentials", "auth"}
    
    @staticmethod
    def generate_config_fingerprint(config: Dict[str, Any]) -> str:
        """
        Generates a deterministic hash from a configuration dictionary,
        explicitly scrubbing any sensitive keys to prevent leakage.
        """
        clean_config = FingerprintGenerator._redact_secrets(config)
        # Canonicalize dictionary sorting for determinism
        canonical_str = json.dumps(clean_config, sort_keys=True)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
        
    @staticmethod
    def generate_dataset_fingerprint(dataset_identity: str, schema_version: str, ordered_rows_hash: str) -> str:
        """
        Combines deterministic dataset components into a unified fingerprint.
        Do NOT pass raw arrays here, pass canonical representations.
        """
        base = f"{dataset_identity}|{schema_version}|{ordered_rows_hash}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    @staticmethod
    def _redact_secrets(data: Any) -> Any:
        if isinstance(data, dict):
            clean = {}
            for k, v in data.items():
                if any(sec in k.lower() for sec in FingerprintGenerator.SENSITIVE_KEYS):
                    clean[k] = "[REDACTED]"
                else:
                    clean[k] = FingerprintGenerator._redact_secrets(v)
            return clean
        elif isinstance(data, list):
            return [FingerprintGenerator._redact_secrets(item) for item in data]
        else:
            return data
