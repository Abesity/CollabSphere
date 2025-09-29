import os
import hashlib
import hmac
import base64

# Settings
ITERATIONS = 260_000  # Django uses 260,000 by default (2025)
HASH_NAME = "sha256"
SALT_SIZE = 16  # 128-bit salt

def hash_password(password: str) -> str:
    """
    Hash a password using PBKDF2-HMAC-SHA256 with a random salt.
    Returns a string containing algorithm, iterations, salt, and hash.
    """
    salt = os.urandom(SALT_SIZE)
    dk = hashlib.pbkdf2_hmac(HASH_NAME, password.encode(), salt, ITERATIONS)
    return f"pbkdf2${HASH_NAME}${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"

def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a password against the stored hash.
    """
    try:
        algorithm, hash_name, iterations, salt_b64, hash_b64 = stored_hash.split("$")
        assert algorithm == "pbkdf2"
    except Exception:
        return False

    salt = base64.b64decode(salt_b64)
    stored_dk = base64.b64decode(hash_b64)
    iterations = int(iterations)

    new_dk = hashlib.pbkdf2_hmac(hash_name, password.encode(), salt, iterations)
    return hmac.compare_digest(new_dk, stored_dk)
