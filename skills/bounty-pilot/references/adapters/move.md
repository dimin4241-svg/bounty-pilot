# Move / Sui / Aptos adapter

Identify the exact Move VM and network first: Sui's object ownership/versioning/shared objects differ from Aptos resources and account auth. Do not treat them as interchangeable.

Model abilities (copy/drop/store/key), capability creation/transfer/revocation, shared/owned object access, dynamic fields, signer binding, entry functions, package upgrades, generics/type identity, coin supply and custody. On Sui check shared-object mutability, object ID/ownership, transfer-to-object, dynamic field access and version transitions; on Aptos check signer/resource/account boundaries, module friend/capability restrictions, tables, events, upgrade compatibility. Generate multi-transaction tests in the project's native harness. Use Aptos Move Prover only when the specified invariant is supported. Output precise VM-specific reachable transitions, not EVM analogies.
