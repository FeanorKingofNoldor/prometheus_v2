#!/usr/bin/env python3
"""
Generate Python stub files from PlantUML component diagram.

This creates skeleton implementations with proper type hints and NotImplementedError
so we can validate the architecture with static type checkers (mypy) before writing
actual implementation.
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple

# Map PlantUML types to Python types
TYPE_MAP = {
    "str": "str",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "date": "date",
    "datetime": "datetime",
    "Dict": "Dict",
    "List": "List",
    "Tuple": "Tuple",
    "ndarray": "np.ndarray",
    "DataFrame": "pd.DataFrame",
    "Series": "pd.Series",
    "Tensor": "torch.Tensor",
    "Connection": "Connection",
    "Session": "Session",
}


def parse_method_signature(line: str) -> Tuple[str, str, List[Tuple[str, str]], str]:
    """
    Parse PlantUML method line like:
    +get_regime(as_of_date: date, region: str) : RegimeState
    
    Returns: (visibility, method_name, params, return_type)
    """
    # Remove leading +/- and whitespace
    line = line.strip()
    visibility = "public" if line.startswith("+") else "private"
    line = line[1:].strip()
    
    # Split at :
    if " : " in line:
        signature, return_type = line.split(" : ", 1)
        return_type = return_type.strip()
    else:
        signature = line
        return_type = "None"
    
    # Parse method name and params
    if "(" in signature:
        method_name = signature[:signature.index("(")].strip()
        params_str = signature[signature.index("(")+1:signature.rindex(")")].strip()
        
        params = []
        if params_str:
            for param in params_str.split(","):
                param = param.strip()
                if ":" in param:
                    name, ptype = param.split(":", 1)
                    params.append((name.strip(), ptype.strip()))
                else:
                    params.append((param, "Any"))
    else:
        method_name = signature
        params = []
    
    return visibility, method_name, params, return_type


def generate_class_stub(class_name: str, methods: List[str], is_dataclass: bool = False) -> str:
    """Generate Python class stub code."""
    
    imports = {
        "from typing import Dict, List, Tuple, Any, Optional",
        "from datetime import date, datetime",
        "import numpy as np",
        "import pandas as pd",
    }
    
    if is_dataclass:
        imports.add("from dataclasses import dataclass")
    
    lines = []
    lines.append("# Auto-generated stub - DO NOT EDIT")
    lines.append("# Generated from PlantUML component diagram")
    lines.append("")
    for imp in sorted(imports):
        lines.append(imp)
    lines.append("")
    lines.append("")
    
    if is_dataclass:
        lines.append("@dataclass")
    
    lines.append(f"class {class_name}:")
    lines.append(f'    """Stub for {class_name}."""')
    lines.append("")
    
    if not methods:
        lines.append("    pass")
        return "\n".join(lines)
    
    for method_line in methods:
        if not method_line.strip() or method_line.strip().startswith("--"):
            continue
            
        try:
            visibility, method_name, params, return_type = parse_method_signature(method_line)
            
            # Build parameter list
            param_strs = ["self"]
            for pname, ptype in params:
                param_strs.append(f"{pname}: {ptype}")
            
            params_joined = ", ".join(param_strs)
            
            # Build method
            lines.append(f"    def {method_name}({params_joined}) -> {return_type}:")
            lines.append(f'        """TODO: Implement {method_name}."""')
            lines.append(f'        raise NotImplementedError("{class_name}.{method_name} not implemented")')
            lines.append("")
            
        except Exception as e:
            lines.append(f"    # Error parsing: {method_line}")
            lines.append(f"    # {str(e)}")
            lines.append("")
    
    return "\n".join(lines)


def main():
    """Generate stub files for core packages."""
    
    output_dir = Path("prometheus_stubs")
    output_dir.mkdir(exist_ok=True)
    
    # Example: RegimeEngine
    regime_methods = [
        "+get_regime(as_of_date: date, region: str) : RegimeState",
        "+get_history(start_date: date, end_date: date, region: str) : List[RegimeState]",
        "+get_transition_matrix(region: str) : Dict[str, Dict[str, float]]",
        "-_compute_window_embedding(market_id: str, as_of_date: date) : np.ndarray",
        "-_classify_regime(embedding: np.ndarray) : str",
        "-_compute_confidence(embedding: np.ndarray, regime: str) : float",
    ]
    
    regime_stub = generate_class_stub("RegimeEngine", regime_methods)
    
    regime_file = output_dir / "regime_engine.py"
    regime_file.write_text(regime_stub)
    
    print(f"Generated: {regime_file}")
    print("\nExample stub content:")
    print(regime_stub[:500] + "...")
    
    print("\n" + "="*60)
    print("Next steps:")
    print("1. Run: mypy prometheus_stubs/  # Type check stubs")
    print("2. Write integration tests that call these methods")
    print("3. Tests will fail with NotImplementedError - that's expected!")
    print("4. Gradually replace NotImplementedError with real implementation")


if __name__ == "__main__":
    main()
