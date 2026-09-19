import os
import re

strategy_methods = {
    'breakout.py': """
    def get_parameters(self) -> dict:
        return {
            "lookback_period": self.lookback_period,
            "volume_period": self.volume_period
        }
""",
    'mean_reversion.py': """
    def get_parameters(self) -> dict:
        return {
            "ma_period": self.ma_period,
            "std_dev_mult": self.std_dev_mult
        }
""",
    'trend_following.py': """
    def get_parameters(self) -> dict:
        return {
            "fast_ma": self.fast_ma,
            "slow_ma": self.slow_ma
        }
""",
    'adaptive.py': """
    def get_parameters(self) -> dict:
        return {
            "fast_ma": self.fast_ma,
            "slow_ma": self.slow_ma,
            "atr_period": self.atr_period,
            "volatility_lookback": self.volatility_lookback
        }
""",
    'ensemble.py': """
    def get_parameters(self) -> dict:
        return {
            "strategies": [s.name for s in self.strategies],
            "min_score": self.min_score
        }
"""
}

base_dir = "app/strategies"
for filename, method in strategy_methods.items():
    filepath = os.path.join(base_dir, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            content = f.read()
        
        if "def get_parameters" not in content:
            pattern = re.compile(r'(\s+@property\s+def name\(self\).*?return.*?)\s+def generate_signal', re.DOTALL)
            match = pattern.search(content)
            if match:
                new_content = content[:match.end(1)] + "\n" + method + "\n    def generate_signal" + content[match.end():]
                with open(filepath, 'w') as f:
                    f.write(new_content)
                print(f"Patched {filename}")
            else:
                print(f"Could not find injection point in {filename}")
