# Integration auth agent — who may call the callback

Every protocol has entry points it does not think of as entry points: callbacks, hooks, compose
handlers, relayer and keeper endpoints, flash-loan receivers, bridge message handlers, permit
targets. They are written as if only the intended caller reaches them. **The attacker's question is
not "who calls this" but "which parameters are attacker-controlled, and which of them is actually
validated".**

## Procedure — the parameter authorization matrix

1. Enumerate every function reachable from outside that is not a plain user action: anything named
   `on*`, `*Callback`, `*Received`, `execute*`, `handle*`, `lz*`, `*Hook`, `before*`/`after*`, any
   function the project's own docs describe as called by another system, and every function with a
   `msg.sender == <trusted>` check.
2. For each one, build a row per parameter: where does this value come from, is it inside the
   authenticated envelope or outside it, and is it checked.
3. **Find the field that is trusted but unchecked.** The common shape: the handler verifies that
   `msg.sender` is the trusted framework contract, then reads the real identity from a payload the
   framework copied from the attacker. Verifying the messenger does not verify the message.
4. For each framework, read its own source to learn **who may make it call you**. A queue or compose
   mechanism that any address can enqueue into makes your `msg.sender` check worthless for identity.
   This is the single most productive step in this lens, and it requires reading the dependency,
   not the integration.
5. Check the reverse direction too: values your contract passes outward that the callee authorises
   on, and refund, retry and failure paths where a second call arrives with partially updated state.
6. Check re-entrancy of identity, not just of funds: a hook that is re-entered with a stale
   authenticated identity, a nonce consumed before the body executes, a replay across chains because
   the domain is not bound.

## Where the money is

- A cross-chain handler that validates the source endpoint id and sender from inside the message,
  while both of those fields came from the message.
- A flash-loan or swap callback that does not verify the initiator, so parameters can be injected by
  a third party who triggers the pool directly.
- A keeper endpoint whose parameters set prices, caps or recipients, guarded only by "the keeper will
  pass sane values".
- A permit or signature path where the signed intent does not bind the recipient, the chain, the
  nonce or the amount actually executed.
- A handler whose authorised-caller list was configured permissively on one chain only — check the
  live configuration, not the setter.

## Proof standard

Name the parameter, quote the check that exists, quote the absence of the check that matters, and
show from the framework's own code that an unprivileged address can produce that call. For a live
protocol, read the configured peers, endpoints and authorised callers on chain and cite the block.
