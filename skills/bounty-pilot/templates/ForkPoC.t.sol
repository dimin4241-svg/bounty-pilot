// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// Fork PoC against a DEPLOYED protocol.
//   forge test --match-path ForkPoC.t.sol -vvvv
// Pin the block. An unpinned fork test is not reproducible evidence.
//
// Fill every <...> and delete the guidance comments before attaching this to a report.

import {Test, console2} from "forge-std/Test.sol";

interface ITarget {
    // Only the functions the PoC calls. Do not copy the implementation in —
    // the point of a fork test is that the deployed implementation is used.
    function <stateReader>() external view returns (uint256);
    function <attackEntryPoint>(uint256 amount) external;
}

contract ForkPoC is Test {
    // ---- pinned environment -------------------------------------------------
    uint256 constant FORK_BLOCK = <block number>;          // the block this was observed at
    string  constant RPC_ENV    = "<RPC_ENV_VAR>";          // read from env, never hardcode a key

    ITarget constant TARGET = ITarget(<0xdeployed address>);
    address constant VICTIM = <0x... an address that already holds the position at risk>;

    address attacker = makeAddr("attacker");                // no private keys anywhere

    function setUp() public {
        vm.createSelectFork(vm.envString(RPC_ENV), FORK_BLOCK);
        vm.label(address(TARGET), "target");
        // Fund the attacker only with what the attack genuinely needs, and say what that is.
        deal(attacker, <capital the attacker must supply> ether);
    }

    // ---- the finding --------------------------------------------------------
    function test_<property>_breaks() public {
        uint256 before = TARGET.<stateReader>();
        console2.log("property before", before);

        vm.startPrank(attacker);
        TARGET.<attackEntryPoint>(<attacker-chosen value>);
        vm.stopPrank();

        uint256 after_ = TARGET.<stateReader>();
        console2.log("property after", after_);

        // Assert the PROPERTY, and name it in the message. Not "it reverted".
        assertEq(after_, <what a correct implementation would hold>,
            "<the aggregate/balance/liability that must have changed and did not>");
    }

    // ---- negative control ---------------------------------------------------
    // Same sequence, one attacker capability removed (or against the patched code).
    // This is what tells a reviewer the harness is not the finding.
    function test_control_<property>_holds() public {
        uint256 before = TARGET.<stateReader>();

        vm.startPrank(attacker);
        TARGET.<attackEntryPoint>(<the benign value, or the privileged path>);
        vm.stopPrank();

        assertEq(TARGET.<stateReader>(), before + <the expected change>,
            "control: the same path behaves correctly without the attacker capability");
    }

    // ---- quantification -----------------------------------------------------
    // The report needs numbers, not adjectives. Print what moved and what it cost.
    function test_quantify_impact() public {
        uint256 attackerBefore = attacker.balance;
        uint256 victimBefore   = <victim's accounted balance>;

        // ... run the attack ...

        console2.log("attacker net", int256(attacker.balance) - int256(attackerBefore));
        console2.log("victim loss",  victimBefore - <victim's accounted balance after>);
        console2.log("gas/capital required: see -vvvv trace and the deal() above");
    }
}
