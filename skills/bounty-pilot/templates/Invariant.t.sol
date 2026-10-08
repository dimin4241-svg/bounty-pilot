// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// Invariant PoC. Use this when you believe a property must always hold but cannot name the exact
// sequence that breaks it. The fuzzer finds the sequence; the counterexample it prints IS the PoC.
//
//   forge test --match-path Invariant.t.sol -vvv
//   (fail_on_revert = false hides real bugs behind reverts — keep it true and clamp inputs instead)
//
// If the project already has an invariant suite, extend it rather than starting over, and say which
// invariant you added. For Echidna/Medusa suites, pashov's `fizz` skill generates a full harness;
// a broken invariant from a generated suite is the same quality of evidence as this.

import {Test} from "forge-std/Test.sol";
import {StdInvariant} from "forge-std/StdInvariant.sol";
import {<Target>} from "<relative path into the unmodified target repo>";

/// @dev The handler is what makes this honest: it exposes ONLY the calls an unprivileged actor can
///      make, with inputs clamped to values that actor could really supply. A handler that calls
///      admin functions proves nothing about an attacker.
contract Handler is Test {
    <Target> public target;
    address[] internal actors;

    constructor(<Target> target_) {
        target = target_;
        actors.push(makeAddr("alice"));
        actors.push(makeAddr("bob"));
    }

    function _actor(uint256 seed) internal view returns (address) {
        return actors[seed % actors.length];
    }

    function deposit(uint256 actorSeed, uint256 amount) external {
        amount = bound(amount, 1, 1e24);          // clamp, do not reject: a rejected input is a lost run
        vm.startPrank(_actor(actorSeed));
        target.<deposit>(amount);
        vm.stopPrank();
    }

    function withdraw(uint256 actorSeed, uint256 amount) external {
        amount = bound(amount, 0, 1e24);          // include 0 and the maximum deliberately
        vm.startPrank(_actor(actorSeed));
        target.<withdraw>(amount);
        vm.stopPrank();
    }

    // Add one function per unprivileged entry point. The invariant can only break through a call
    // the handler exposes, so a missing entry point is a missing bug.
}

contract InvariantPoC is StdInvariant, Test {
    <Target> target;
    Handler handler;

    function setUp() public {
        target = new <Target>(<arguments from the project's deploy script>);
        handler = new Handler(target);
        targetContract(address(handler));
    }

    /// The property, in words: <state it here, e.g. "the sum of per-user debt equals totalDebt">
    function invariant_<property>() public view {
        assertEq(target.<aggregate>(), <recomputed from first principles>,
            "<the property, in words, so the counterexample is readable>");
    }

    /// Solvency-shaped properties are the highest-value ones: assets held must cover liabilities
    /// recorded, always, after any sequence.
    function invariant_solvency() public view {
        assertGe(<assets actually held>, <liabilities recorded>,
            "recorded liabilities must never exceed assets held");
    }
}
