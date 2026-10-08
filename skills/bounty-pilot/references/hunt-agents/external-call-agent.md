# External call agent — arbitrary targets and the approvals waiting for them

One shape has drained production protocols more times than any other in recent years: a contract
that performs an **external call to a target and with calldata the caller supplies**, while token
approvals sit on it. Routers, aggregators, zappers, bridge adapters, swap helpers, multicall
utilities, batch executors, "execute arbitrary action" modules. The exploit is not subtle, it is
repetitive — and it keeps shipping because each individual function looks like plumbing.

## Procedure

1. **Find every outbound call whose destination is not a constant.** Grep for `.call(`,
   `.delegatecall(`, `.staticcall(`, `functionCall`, `Address.call*`, assembly `call`/`delegatecall`,
   and any function taking a `target`/`to`/`router`/`adapter`/`callee`/`swapper` address, or a
   `bytes` payload, or a `Call[]`/`Action[]`/`Step[]` struct array.
2. **For each, answer four questions in writing:**
   - Who chooses the target, and is it checked against a whitelist that is actually populated?
   - Who chooses the calldata, and is the selector constrained?
   - What does this contract hold or control at that moment: token balances, **approvals granted by
     users**, approvals it granted to others, native balance, its own privileged roles?
   - What is `msg.sender` from the callee's point of view — can this contract be made to call a
     token's `transferFrom`, a vault's `withdraw`, or its own privileged setter?
3. **Hunt the approval residue.** Users approve a router once and it stays approved. So an arbitrary
   call from the router can move *their* tokens, not just the router's. Check: infinite approvals,
   approvals not reset after a swap, approvals granted to an adapter that itself takes arbitrary
   calls, and `permit` signatures a helper can replay into a different action.
4. **Hunt the self-call.** Can the arbitrary target be the contract itself? Then the attacker reaches
   every `internal`-but-externally-reachable function with `msg.sender == address(this)`, and any
   guard written as "only this contract" is now open.
5. **Hunt delegatecall specifically.** A `delegatecall` to an attacker-chosen address executes in
   this contract's storage: owner slots, balances, proxy implementation pointer. Any unconstrained
   `delegatecall` is critical until proven otherwise. Check library addresses that are settable, and
   modules loaded from a registry an attacker can register into.
6. **Hunt the return path.** Unchecked success flags; `returndata` copied into memory with a
   caller-controlled length; a decode that assumes a shape; a zero-length return read as a value;
   a gas stipend that lets the callee fail silently; try/catch that swallows a revert and continues
   with half-updated state.
7. **Hunt the callback direction too.** The call hands control to the callee *mid-function*. What
   state is half-written at that moment, what does the callee see, and what can it re-enter —
   including read-only re-entrancy where it only *reads* a value this function has temporarily
   broken, and a third protocol prices off that read.

## Where the money is

- A route/step array where one step's target or selector is unvalidated.
- A whitelist that is checked but empty, or enforced on the first hop and not on the hops a
  whitelisted adapter then makes.
- `delegatecall` with a settable implementation, library or module address.
- Leftover approvals plus any arbitrary-call surface in the same contract — that combination alone
  is worth writing up.
- A refund or sweep helper that sends "whatever is left" to a caller-chosen recipient.
- A permit-and-act helper where the permit and the action are bound to different parameters.

## Proof standard

Build the exact call the attacker makes: the target, the selector, the encoded arguments, and the
pre-existing approval or balance it consumes. A PoC here is short and unambiguous — if you cannot
construct the call, you have a LEAD, not a finding. Name every whitelist you checked and whether it
was populated **on chain**, not in the deploy script.
