# Zantara Frontend (Mouth)

The frontend interface for the Zantara Intelligent Business Operating System. Built with Next.js 14, Tailwind CSS, and TypeScript.

## Features

- **Modern Chat Interface**: Real-time streaming chat with the Zantara AI.
- **Team Status**: Clock-in/out functionality and team visibility.
- **WebSocket Integration**: Real-time updates for notifications and messages.
- **Responsive Design**: Mobile-first approach with a sleek, dark-themed UI.
- **Secure**: Token-based authentication and secure WebSocket connections.

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS v4
- **State Management**: React Hooks (Custom hooks for Chat, WebSocket, Team Status)
- **Testing**: Vitest (Unit), Playwright (E2E)
- **Icons**: Lucide React

## Getting Started

1.  **Install dependencies:**

    ```bash
    npm install
    ```

2.  **Run the development server:**

    ```bash
    npm run dev
    ```

3.  **Open [http://localhost:3000](http://localhost:3000)**

## Scripts

- `npm run dev`: Start development server
- `npm run build`: Build for production
- `npm run start`: Start production server
- `npm run lint`: Run ESLint
- `npm run test`: Run unit tests
- `npm run test:e2e`: Run E2E tests

## Project Structure

- `src/app`: App Router pages and layouts
- `src/components`: Reusable UI components
- `src/hooks`: Custom React hooks
- `src/lib`: Utility functions and API clients
- `public`: Static assets

## Deployment

Deployed on Fly.io. See `fly.toml` for configuration.
