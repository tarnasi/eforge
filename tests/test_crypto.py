"""Tests for the crypto module."""

from environment_forge.crypto import (
    decrypt,
    derive_fernet_key,
    encrypt,
    generate_secret_key,
    get_or_create_secret,
)


def test_generate_secret_key():
    key1 = generate_secret_key()
    key2 = generate_secret_key()
    assert key1 != key2
    assert len(key1) > 30


def test_derive_fernet_key_deterministic():
    k1 = derive_fernet_key("my-secret")
    k2 = derive_fernet_key("my-secret")
    assert k1 == k2


def test_derive_fernet_key_different_secrets():
    k1 = derive_fernet_key("secret-a")
    k2 = derive_fernet_key("secret-b")
    assert k1 != k2


def test_encrypt_decrypt_roundtrip():
    secret = "test-master-key"
    plaintext = "hello world"
    ciphertext = encrypt(plaintext, secret)
    assert ciphertext != plaintext
    assert decrypt(ciphertext, secret) == plaintext


def test_encrypt_produces_different_tokens():
    secret = "key"
    c1 = encrypt("same text", secret)
    c2 = encrypt("same text", secret)
    # Fernet uses a timestamp + random IV, so tokens differ
    assert c1 != c2


def test_get_or_create_secret_generates_and_reads(tmp_path):
    keyfile = tmp_path / "secret.key"
    key1 = get_or_create_secret(keyfile)
    assert keyfile.is_file()
    key2 = get_or_create_secret(keyfile)
    assert key1 == key2


def test_get_or_create_secret_from_env(tmp_path, monkeypatch):
    keyfile = tmp_path / "no-file.key"
    monkeypatch.setenv("EFORGE_SECRET", "env-secret-123")
    key = get_or_create_secret(keyfile)
    assert key == "env-secret-123"
    assert not keyfile.is_file()
