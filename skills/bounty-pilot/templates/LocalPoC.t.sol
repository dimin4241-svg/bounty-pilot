// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// Local PoC: the production contracts are deployed into a clean chain and driven into the
// vulnerable state through ordinary calls. Use this when the target is not deployed, or when the
// state you need cannot be reached on a fork.
//
//   forge test --match-path LocalPoC.t.sol -vvvv
//
// RULE: import the real contracts. Every mock you substitute weakens the evidence, and a mock that
// replaces the component under test destroys it. Where a mock is unavoidable, make it behave like
// the real dependency (including its failure modes) and record it as a limitation in the record.

import {Test, console2} from "forge-std/Test.sol";
import {<Target>} from "<relative path into the unmodified target repo>";

contract LocalPoC is Test {
    <Target> target;

    address admin    = makeAddr("admin");
    address victim   = makeAddr("victim");
    address attacker = makeAddr("attacker");

    function setUp() public {
        // Deploy the way the project's own deploy script deploys it — read that script.
        // Wrong constructor arguments produce a PoC of a configuration nobody runs.
        vm.prank(admin);
        target = new <Target>(<arguments taken from the project's deploy script>);

        // Reach the realistic starting state through the protocol's own entry points.
        // Never write storage directly to set up the bug: vm.store makes the state unreachable,
        // and an unreachable state is the first thing triage rejects.
        vm.startPrank(victim);
        // ... ordinary user actions ...
        vm.stopPrank();
    }

    function test_<property>_breaks() public {
        uint256 before = target.<aggregate>();

        vm.prank(attacker);
        target.<entryPoint>(<attacker-chosen value>);

        assertEq(target.<aggregate>(), <what must hold>,
            "<name the invariant in words: 'totalDebt must fall by the amount redeemed'>");
        console2.log("observed", target.<aggregate>(), "expected", <what must hold>);
        before;
    }

    function test_control_<property>_holds() public {
        // The same sequence through the path that does maintain the invariant, proving the
        // mechanism is the specific omission you claim and not the harness.
        vm.prank(victim);
        target.<theSiblingEntryPointThatIsCorrect>(<equivalent value>);
        assertEq(target.<aggregate>(), <the correct value>,
            "control: the sibling path maintains the invariant");
    }
}
