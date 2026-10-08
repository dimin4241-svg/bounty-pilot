# Privileged path agent — how an unprivileged actor gets privileged power

Two facts make this the most valuable lens in the set, and the most neglected.

First, **access control and initialization are the categories automated reviewers measurably miss
most**, even when several models are combined. Second, **privileged-path compromise is the largest
loss category in practice** — the biggest incidents are not broken arithmetic, they are someone
acting with authority they should not have had.

And it is neglected for a bad reason: every checklist says "do not report admin can rug", so
reviewers skip the whole area. That rule is about *the admin behaving badly*. It says nothing about
an unprivileged actor **reaching** admin power, which is a critical finding on every rubric.

## The question you are answering

Not "what can the owner do". It is: **for each privileged capability, enumerate every path that
leads to it, and find the one that does not check who is walking it.**

## Procedure

1. **Enumerate capabilities, not modifiers.** List every action the protocol treats as privileged:
   setting a price source, a cap, a fee, a recipient; pausing; upgrading; granting a role; moving
   funds; registering a market, token or peer; whitelisting a target. For each, write down who is
   supposed to be able to do it.
2. **For each capability, enumerate every path to it.** Grep for the state it writes, not for the
   function name. Privileged state written from two places where only one is guarded is the most
   common shape in this lens. Check: a public wrapper and an internal function reachable another
   way; a batch/multicall that forwards arbitrary calls; a function inherited from a base and not
   overridden; a `delegatecall` that executes attacker-chosen code in this contract's storage.
3. **Attack the guard itself.** Read the modifier body rather than its name:
   - Does it compare against the right variable? `owner` vs `pendingOwner`, `msg.sender` vs
     `tx.origin`, the module's own address vs the module registry.
   - Is it tautological? `require(msg.sender == msg.sender)`, a role check against a role that is
     never granted, a check on a mapping an unprivileged function writes.
   - Does `_authorizeUpgrade`, `_checkRole` or `onlyGovernance` resolve to something configurable,
     and who configures it?
   - Is the authorised party a **contract** with a loose function? Authority delegated to a
     multicall, router, forwarder, relayer or module registry is only as strong as that contract's
     weakest entry point. Follow it in.
4. **Attack initialization.** This is half of this lens's yield:
   - Is `initialize` callable by anyone, once, and has it actually been called **on chain**? Read
     it. An uninitialised owner slot is a live takeover.
   - Can it be called twice — a missing `initializer`, a reused `reinitializer` version, a struct
     re-set by a later migration?
   - Is the **implementation** behind the proxy initialised in its own right, or does it sit there
     with an empty owner slot and a reachable `selfdestruct`/`delegatecall`? This froze 500k ETH
     once and the pattern keeps reappearing.
   - Does the constructor set what the initializer is supposed to set, so a proxy never gets it?
5. **Attack the deployment-time values.** A guard compares against a value somebody configured. If
   that value can be zero, empty, or the attacker's own, the guard is decorative. The Nomad bridge
   lost ~$190M because an upgrade left the trusted root at zero, which made every forged proof
   valid. So for each guard: what does it compare against, what is that set to **right now on
   chain**, and is the zero or default value accepted?
6. **Attack the two-step and timelocked paths.** A pending-owner that anyone can accept; a timelock
   whose queued payload can be replaced; a proposal executable before the delay because the delay
   is read from a field the proposal itself sets; a guardian role that bypasses the timelock;
   governance whose voting power is the **current** balance, so a flash loan is a majority (this
   took ~$180M from Beanstalk).
7. **Attack the signature-authorised paths.** Where privilege arrives as a signed message: is the
   signer set and non-zero; is the domain bound to this chain and this contract; is the nonce
   consumed before the body runs; does `ecrecover` return zero on a malformed signature and does
   zero pass the check; is the message's own claimed sender used instead of the recovered one?

## Where the money is

- An initializer reachable on a live deployment, or an uninitialised implementation.
- A privileged setter reachable through a multicall, batch, or `delegatecall` surface.
- A role that some unprivileged function can grant, including indirectly via a registry.
- A guard comparing against a configurable address that is currently zero or attacker-set.
- Governance power measured by spot balance rather than a snapshot.
- An upgrade authority whose own owner is an EOA, a stale multisig, or a contract with a loose
  function — check the live owner, not the source default.

## Proof standard

Name the capability, quote the guard that was supposed to protect it, show the path that reaches
the same state without it, and read the relevant live values on chain with a pinned block. For an
initialization finding, the live storage slot is the evidence: an owner slot that is zero today is
not a theory.

**Do not** emit "the owner is powerful", "the admin key is an EOA" or "centralisation risk" with no
mechanism. Those are rejected by rule on nearly every program, and filing them makes the rest of
your report read as noise.
