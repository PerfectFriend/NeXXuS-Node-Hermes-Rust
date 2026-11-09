//! Verification-challenges для онбординга: «подтверди, что записал сид».
//!
//! Вендорено из `crates/bip39-auth-rs/src/mnemonic.rs` репозитория
//! PerfectFriend/BIP39-Onboarding-pipeline (Apache-2.0). Логика не менялась:
//! 3 случайные позиции слова, 4 дистрактора из официального wordlist,
//! при повторе с `exclude_indices` — другие позиции (защита от перебора).

use bip39::Language;
use rand::seq::SliceRandom;
use rand::Rng;
use serde::{Deserialize, Serialize};

/// Число слов в сид-фразе.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum WordCount {
    Words12 = 12,
    Words24 = 24,
}

/// Один вопрос верификации: «какое слово было под номером N?»
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationChallenge {
    pub word_index: usize,
    pub display_number: usize,
    pub correct_word: String,
    pub options: Vec<String>,
}

/// Генерирует 3 challenge по словам сид-фразы.
///
/// `exclude_indices` — позиции, уже спрашивавшиеся ранее (при ошибке
/// генерируем заново другие позиции и свежие дистракторы).
pub fn generate_verification_challenges(
    words: &[String],
    exclude_indices: &[usize],
) -> Result<Vec<VerificationChallenge>, String> {
    if words.len() < 3 {
        return Err("Сид-фраза должна содержать минимум 3 слова".to_string());
    }

    let mut rng = rand::thread_rng();
    let total = words.len();
    let target_count = 3.min(total);

    let all_indices: Vec<usize> = (0..total).collect();
    let mut candidate_pool: Vec<usize> = all_indices
        .iter()
        .copied()
        .filter(|i| !exclude_indices.contains(i))
        .collect();
    candidate_pool.shuffle(&mut rng);

    let mut chosen_indices: Vec<usize> = candidate_pool.into_iter().take(target_count).collect();
    if chosen_indices.len() < target_count {
        let mut fallback: Vec<usize> = all_indices
            .into_iter()
            .filter(|i| !chosen_indices.contains(i))
            .collect();
        fallback.shuffle(&mut rng);
        for idx in fallback {
            if chosen_indices.len() < target_count {
                chosen_indices.push(idx);
            }
        }
    }
    chosen_indices.sort();

    let wordlist = Language::English.word_list();
    let mut challenges = Vec::new();

    for &word_index in &chosen_indices {
        let correct_word = words[word_index].clone();
        let mut distractors = std::collections::HashSet::new();
        while distractors.len() < 4 {
            let random_pick = wordlist[rng.gen_range(0..wordlist.len())].to_string();
            if random_pick != correct_word {
                distractors.insert(random_pick);
            }
        }
        let mut options: Vec<String> = std::iter::once(correct_word.clone())
            .chain(distractors)
            .collect();
        options.shuffle(&mut rng);
        challenges.push(VerificationChallenge {
            word_index,
            display_number: word_index + 1,
            correct_word,
            options,
        });
    }

    Ok(challenges)
}

/// Проверяет ответ на challenge.
pub fn check_challenge(challenge: &VerificationChallenge, answer: &str) -> bool {
    challenge.correct_word == answer
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fake_words(n: usize) -> Vec<String> {
        (0..n).map(|i| format!("word{i}")).collect()
    }

    #[test]
    fn challenges_cover_three_positions_with_five_options() {
        let words = fake_words(12);
        let ch = generate_verification_challenges(&words, &[]).unwrap();
        assert_eq!(ch.len(), 3);
        for c in &ch {
            assert_eq!(c.options.len(), 5);
            assert!(c.options.contains(&c.correct_word));
            assert_eq!(c.correct_word, words[c.word_index]);
            assert_eq!(c.display_number, c.word_index + 1);
        }
    }

    #[test]
    fn retry_excludes_previous_indices() {
        let words = fake_words(12);
        let first = generate_verification_challenges(&words, &[]).unwrap();
        let first_idx: Vec<usize> = first.iter().map(|c| c.word_index).collect();
        let second = generate_verification_challenges(&words, &first_idx).unwrap();
        for c in &second {
            assert!(!first_idx.contains(&c.word_index));
        }
    }

    #[test]
    fn too_few_words_rejected() {
        assert!(generate_verification_challenges(&fake_words(2), &[]).is_err());
    }

    #[test]
    fn check_challenge_works() {
        let words = fake_words(12);
        let ch = generate_verification_challenges(&words, &[]).unwrap();
        assert!(check_challenge(&ch[0], &ch[0].correct_word));
        assert!(!check_challenge(&ch[0], "definitely-wrong"));
    }
}
