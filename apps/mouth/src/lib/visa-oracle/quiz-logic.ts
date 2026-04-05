import type { QuizAnswers } from './types';

export type QuizStep = 1 | 2 | 3 | 4;

export interface PurposeOption {
  value: QuizAnswers['purpose'];
  label: string;
  icon: string;
}

export interface DurationOption {
  value: QuizAnswers['duration'];
  label: string;
  description: string;
}

export interface FamilyOption {
  value: QuizAnswers['family'];
  label: string;
  icon: string;
}

export const PURPOSE_OPTIONS: PurposeOption[] = [
  { value: 'visit', label: 'Tourism / Visit', icon: '🏖️' },
  { value: 'work', label: 'Work', icon: '💼' },
  { value: 'invest', label: 'Investment', icon: '📈' },
  { value: 'retire', label: 'Retirement', icon: '🌅' },
  { value: 'digital_nomad', label: 'Digital Nomad', icon: '💻' },
  { value: 'family', label: 'Family Reunification', icon: '👨‍👩‍👧' },
  { value: 'study', label: 'Study', icon: '🎓' },
];

export const DURATION_OPTIONS: DurationOption[] = [
  {
    value: 'short',
    label: 'Short stay',
    description: 'Up to 60 days',
  },
  {
    value: 'medium',
    label: 'Medium stay',
    description: '2 – 12 months',
  },
  {
    value: 'long',
    label: 'Long stay',
    description: '1 – 5 years',
  },
  {
    value: 'permanent',
    label: 'Permanent',
    description: '5+ years / indefinite',
  },
];

export const FAMILY_OPTIONS: FamilyOption[] = [
  { value: 'solo', label: 'Solo', icon: '🧳' },
  { value: 'spouse', label: 'With spouse', icon: '👫' },
  { value: 'children', label: 'With children', icon: '👨‍👧' },
  { value: 'spouse_children', label: 'Spouse & children', icon: '👨‍👩‍👧‍👦' },
];

export function getStepTitle(step: QuizStep): string {
  switch (step) {
    case 1:
      return 'What is your nationality?';
    case 2:
      return 'What is your main purpose for coming to Bali?';
    case 3:
      return 'How long do you plan to stay?';
    case 4:
      return 'Who are you travelling with?';
  }
}

export function isQuizComplete(answers: Partial<QuizAnswers>): answers is QuizAnswers {
  return (
    typeof answers.nationality === 'string' &&
    answers.nationality.length > 0 &&
    answers.purpose !== undefined &&
    answers.duration !== undefined &&
    answers.family !== undefined
  );
}
