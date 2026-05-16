"""M-Pesa configuration.

Phase 3 ships code-complete but credential-free (docs/PLAN.md §8). The
rule: if Daraja credentials are absent, the system uses the stub adapter
(no network, logs intent to the audit trail) so the *entire* flow —
webhooks, reconciliation, STK initiation — is testable and demoable
without a live merchant account. When the chapter activates the Paybill,
filling the env vars flips it to the real Daraja adapter with zero code
change.
"""

from __future__ import annotations

from dataclasses import dataclass

from decouple import config


@dataclass(frozen=True)
class MpesaSettings:
    consumer_key: str
    consumer_secret: str
    paybill: str
    passkey: str
    callback_url: str
    validation_url: str
    confirmation_url: str
    environment: str  # "sandbox" | "production"

    @property
    def has_credentials(self) -> bool:
        """True only when the operational secrets are all present.

        callback URLs have safe defaults, so they don't count toward
        "configured". The merchant secrets do.
        """
        return all(
            [
                self.consumer_key,
                self.consumer_secret,
                self.paybill,
                self.passkey,
            ]
        )

    @property
    def base_api_url(self) -> str:
        if self.environment == "production":
            return "https://api.safaricom.co.ke"
        return "https://sandbox.safaricom.co.ke"


def load_settings() -> MpesaSettings:
    return MpesaSettings(
        consumer_key=config("MPESA_CONSUMER_KEY", default=""),
        consumer_secret=config("MPESA_CONSUMER_SECRET", default=""),
        paybill=config("MPESA_PAYBILL", default=""),
        passkey=config("MPESA_PASSKEY", default=""),
        callback_url=config(
            "MPESA_CALLBACK_URL",
            default="https://kuppetmsa.co.ke/api/v1/mpesa/callback/",
        ),
        validation_url=config(
            "MPESA_VALIDATION_URL",
            default="https://kuppetmsa.co.ke/api/v1/mpesa/validate/",
        ),
        confirmation_url=config(
            "MPESA_CONFIRMATION_URL",
            default="https://kuppetmsa.co.ke/api/v1/mpesa/confirm/",
        ),
        environment=config("MPESA_ENV", default="sandbox"),
    )
