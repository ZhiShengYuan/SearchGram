#!/usr/bin/env python3
# coding: utf-8

"""
SearchGram Key Generation Script

Generates Ed25519 keypair for JWT authentication between services.
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from searchgram.jwt_utils import generate_ed25519_keypair


def main():
    parser = argparse.ArgumentParser(
        description="Generate Ed25519 keypair for SearchGram JWT authentication"
    )
    parser.add_argument(
        "--private-key",
        default="keys/private.key",
        help="Path to save private key (default: keys/private.key)",
    )
    parser.add_argument(
        "--public-key",
        default="keys/public.key",
        help="Path to save public key (default: keys/public.key)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing keys",
    )

    args = parser.parse_args()

    # Check if keys already exist
    private_path = Path(args.private_key)
    public_path = Path(args.public_key)

    if private_path.exists() or public_path.exists():
        if not args.force:
            print("⚠️  Keys already exist!")
            print(f"   Private key: {private_path} (exists: {private_path.exists()})")
            print(f"   Public key: {public_path} (exists: {public_path.exists()})")
            print("\nUse --force to overwrite existing keys.")
            return 1

        print("⚠️  Overwriting existing keys...")

    # Generate keypair
    print("Generating Ed25519 keypair for JWT authentication...")
    print()

    try:
        generate_ed25519_keypair(str(private_path), str(public_path))

        print()
        print("✅ Keypair generated successfully!")
        print()
        print(f"📁 Files created:")
        print(f"   Private key: {private_path.absolute()} (mode 600)")
        print(f"   Public key:  {public_path.absolute()} (mode 644)")
        print()
        print("📋 Next steps:")
        print("1. Update config.json with these paths:")
        print(f'   "auth": {{')
        print(f'     "use_jwt": true,')
        print(f'     "private_key_path": "{private_path}",')
        print(f'     "public_key_path": "{public_path}"')
        print(f'   }}')
        print()
        print("2. Copy keys to Go search service directory:")
        print(f"   cp {private_path} {public_path} searchgram-engine/keys/")
        print()
        print("3. Update searchgram-engine/config.yaml:")
        print(f"   auth:")
        print(f"     use_jwt: true")
        print(f"     public_key_path: keys/public.key")
        print(f"     private_key_path: keys/private.key")
        print()
        print("⚠️  IMPORTANT: Keep private.key secret and secure!")
        print("   Do NOT commit private.key to version control.")
        print()

        return 0

    except Exception as e:
        print(f"\n❌ Error generating keys: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
