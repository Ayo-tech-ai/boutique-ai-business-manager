"""
Google API key rotation for the Boutique AI Business Manager.

Supports two Google/Gemini API keys (e.g. from two separate Google
accounts) and automatically fails over from one to the other when
the active key's free-tier daily quota is exhausted.

SCOPE: this is a solo-testing/demo convenience, not a production
pattern. In a real client deployment, the client uses their own
paid API key (or pays you to cover it) — key rotation to stretch
free-tier limits has no place there.

How it works:
- Two keys are read from secrets/env: GOOGLE_API_KEY_1, GOOGLE_API_KEY_2
- The active key is tracked in Streamlit's session state (per-process
  really, since ADK's Gemini client reads the key from the
  GOOGLE_API_KEY environment variable at call time).
- When a call fails with a quota/rate-limit error (HTTP 429 /
  RESOURCE_EXHAUSTED), we swap the active key and retry the SAME
  request once. If the second key also fails, the error is raised
  to the caller.
"""

import os


class KeyRotationExhausted(Exception):
    """Raised when both keys have hit their quota."""
    pass


def _is_quota_error(exception):
    """Best-effort detection of a quota/rate-limit error from the
    Gemini API. Checks the exception's string representation for the
    telltale markers Google's API returns, since the exact exception
    class can vary depending on the underlying transport (google-genai
    SDK vs REST)."""
    message = str(exception).lower()
    markers = [
        "429",
        "resource_exhausted",
        "resource exhausted",
        "quota",
        "rate limit",
        "rate_limit",
    ]
    return any(marker in message for marker in markers)


class GoogleKeyRotator:
    """
    Holds two Google API keys and manages which one is currently
    active via the GOOGLE_API_KEY environment variable.
    """

    def __init__(self, key_1, key_2):
        if not key_1 and not key_2:
            raise ValueError("At least one Google API key must be provided.")

        # Filter out any missing key so rotation still works with just one.
        self.keys = [k for k in (key_1, key_2) if k]
        self.active_index = 0
        self._apply_active_key()

    def _apply_active_key(self):
        os.environ["GOOGLE_API_KEY"] = self.keys[self.active_index]

    def current_key_label(self):
        """Returns a human-readable label for logging/debugging,
        never the key itself."""
        return f"key_{self.active_index + 1}_of_{len(self.keys)}"

    def rotate(self):
        """Switches to the next key in the list, if one exists.
        Returns True if a different key is now active, False if
        there's no other key to switch to (single-key setup, or
        we've already tried all keys in this cycle)."""
        if len(self.keys) < 2:
            return False

        self.active_index = (self.active_index + 1) % len(self.keys)
        self._apply_active_key()
        return True

    async def call_with_failover(self, async_fn, *args, **kwargs):
        """
        Calls async_fn(*args, **kwargs), retrying once per additional
        key on a quota-exceeded error. Raises KeyRotationExhausted if
        every key has been tried and all failed with quota errors.
        Any non-quota error is raised immediately without retrying,
        since rotating keys won't fix a real bug or bad request.
        """
        attempts = len(self.keys)
        last_error = None

        for attempt in range(attempts):
            try:
                return await async_fn(*args, **kwargs)
            except Exception as e:
                if not _is_quota_error(e):
                    # Not a quota issue — don't waste the other key on it.
                    raise

                last_error = e
                if attempt < attempts - 1:
                    self.rotate()
                # else: this was the last key, fall through to raise below

        raise KeyRotationExhausted(
            f"All {attempts} Google API key(s) hit their quota limit. "
            f"Last error: {last_error}"
        )
