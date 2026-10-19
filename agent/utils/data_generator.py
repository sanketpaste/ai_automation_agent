import random
import string
import time
from typing import Dict

def random_string(length: int = 6) -> str:
    """Generates a random lowercase alphanumeric string."""
    chars: str = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=length))

def generate_user() -> Dict[str, str]:
    """
    Generates a unique random user without external API dependencies.
    Satisfies dummy app validation:
    - Name: Non-empty string
    - Email: Contains '@' and '.'
    - Phone: Digits string
    - Password: Min 8 chars
    """
    uid: str = f"{random_string(5)}_{int(time.time()) % 10000}"
    name: str = f"Test User {uid}"
    email: str = f"user_{uid}@testcorp.io"
    phone: str = f"555{random.randint(1000000, 9999999)}"
    password: str = f"SecureP@ss_{random_string(4)}"

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "password": password
    }
