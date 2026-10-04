from procore_mcp import (
    GENESIS_PREV_SIGNATURE,
    ActionStatus,
    AuditedFastMCP,
    AuditEntry,
    AuditLogManager,
    SecretString,
    VaultResolutionError,
    __version__,
    compute_entry_signature,
    compute_payload_digest,
    create_server,
    main,
    resolve_1password,
    resolve_aws_secrets,
    resolve_env,
    resolve_hashicorp_vault,
    resolve_secret,
    run_audit_inspect,
    run_audit_verify,
    verify_audit_log,
)


def test_version() -> None:
    assert __version__ == "0.1.0"
    assert callable(create_server)
    assert callable(main)
    assert callable(run_audit_verify)
    assert callable(run_audit_inspect)
    assert callable(verify_audit_log)
    assert callable(compute_payload_digest)
    assert callable(compute_entry_signature)
    assert callable(resolve_secret)
    assert callable(resolve_1password)
    assert callable(resolve_aws_secrets)
    assert callable(resolve_hashicorp_vault)
    assert callable(resolve_env)
    assert AuditLogManager is not None
    assert AuditEntry is not None
    assert ActionStatus is not None
    assert AuditedFastMCP is not None
    assert SecretString is not None
    assert VaultResolutionError is not None
    assert GENESIS_PREV_SIGNATURE == "0" * 64
