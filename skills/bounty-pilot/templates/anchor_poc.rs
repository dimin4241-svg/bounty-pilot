// Solana PoC. Account substitution and PDA findings must be shown by constructing the instruction
// with the substituted account and observing it succeed — prose does not establish this.
//
// Either harness works; litesvm is faster, solana-program-test is closer to the runtime:
//   cargo test --test poc -- --nocapture
//
// RULES
//   * Load the program under test unmodified: the built .so of the target repo, or the on-chain
//     program dumped with `solana program dump <program-id> target.so`. Dumping the deployed
//     program is also how you prove the live code and the repo agree.
//   * Never load a funded keypair. Every signer here is generated for the test.
//   * A Rust panic is one failed transaction, not a chain halt. Describe impact as what the
//     SUCCEEDING transaction took or broke.

use litesvm::LiteSVM;
use solana_sdk::{
    instruction::{AccountMeta, Instruction},
    pubkey::Pubkey,
    signature::{Keypair, Signer},
    transaction::Transaction,
};

const PROGRAM_ID: Pubkey = solana_sdk::pubkey!("<program id>");

fn setup() -> (LiteSVM, Keypair) {
    let mut svm = LiteSVM::new();
    // The unmodified program, built from the target repo or dumped from chain.
    svm.add_program_from_file(PROGRAM_ID, "<path>/target.so").unwrap();
    let attacker = Keypair::new();
    svm.airdrop(&attacker.pubkey(), 10_000_000_000).unwrap();
    (svm, attacker)
}

#[test]
fn substituted_account_is_accepted() {
    let (mut svm, attacker) = setup();

    // 1. Reach the realistic starting state through the program's own instructions.
    //    Do not write account data directly: an unreachable state is rejected in triage.

    // 2. Build the instruction the way the program expects it, then swap exactly ONE account for
    //    one the attacker controls (or that belongs to another market/user/mint).
    let victim_position: Pubkey = /* derived or created above */ Pubkey::new_unique();
    let attacker_destination = Keypair::new().pubkey();

    let ix = Instruction {
        program_id: PROGRAM_ID,
        accounts: vec![
            AccountMeta::new(victim_position, false),              // <- not owned by the signer
            AccountMeta::new_readonly(attacker.pubkey(), true),    // <- the only signer
            AccountMeta::new(attacker_destination, false),         // <- the substituted account
            // ... the remaining accounts, exactly as the IDL orders them
        ],
        data: vec![/* discriminator + borsh args; take the discriminator from the IDL */],
    };

    let tx = Transaction::new_signed_with_payer(
        &[ix],
        Some(&attacker.pubkey()),
        &[&attacker],
        svm.latest_blockhash(),
    );

    // 3. The finding is that this SUCCEEDS. Assert that, then assert the resulting state.
    let result = svm.send_transaction(tx);
    assert!(result.is_ok(), "the program accepted a substituted account: {result:?}");

    let moved = svm.get_account(&attacker_destination).unwrap();
    assert!(moved.lamports > 0, "value reached an account the attacker chose");
}

#[test]
fn control_correct_account_path() {
    // The negative control: the same instruction with the account the program intended.
    // It must succeed with the correct outcome, proving the harness builds valid instructions and
    // that the first test's success comes from the substitution and nothing else.
    let (mut _svm, _attacker) = setup();
}
