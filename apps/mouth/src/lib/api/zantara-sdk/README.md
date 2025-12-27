# Zantara Frontend SDK

Complete TypeScript SDK and React components for integrating Zantara capabilities into any frontend application.

## Installation

The SDK is already included in the `mouth` app. For external use, import from:

```typescript
import { ZantaraSDK, createZantaraSDK } from '@/lib/api/zantara-sdk';
```

## Quick Start

### Initialize SDK

```typescript
import { createZantaraSDK } from '@/lib/api/zantara-sdk';

const sdk = createZantaraSDK({
  baseUrl: 'https://api.zantara.com',
  apiKey: 'your-api-key', // Optional
  timeout: 30000, // Optional, default 30s
});
```

### Use Agentic RAG Streaming (Zantara AI v2.0)

```typescript
import { useChat } from '@/hooks/useChat';

function ChatComponent() {
  const { sendMessage, isStreaming, response } = useChat();

  const handleQuery = async () => {
    await sendMessage('How to set up PT PMA?');
  };

  return (
    <div>
      {isStreaming && <div>Zantara AI is thinking...</div>}
      {response && <div>{response}</div>}
    </div>
  );
}
```

**Note**: Zantara AI v2.0 uses a single-LLM architecture powered by Gemini 3 Flash.

### Use Memory Components

```typescript
import { MemoryContext } from '@/components/memory/MemoryContext';

function UserProfile({ userId }: { userId: string }) {
  return (
    <MemoryContext
      userId={userId}
      sdk={sdk}
      readonly={false}
    />
  );
}
```

### Use Journey Tracker

```typescript
import { JourneyProgressTracker } from '@/components/journey/JourneyProgressTracker';

function ClientJourney({ journeyId }: { journeyId: string }) {
  return (
    <JourneyProgressTracker
      journeyId={journeyId}
      sdk={sdk}
      onStepClick={(step) => console.log('Step clicked:', step)}
    />
  );
}
```

### Use Compliance Calendar

```typescript
import { ComplianceCalendar } from '@/components/compliance/ComplianceCalendar';

function ComplianceDashboard({ clientId }: { clientId?: string }) {
  return (
    <ComplianceCalendar
      clientId={clientId}
      sdk={sdk}
      daysAhead={90}
      onAlertClick={(alert) => console.log('Alert clicked:', alert)}
    />
  );
}
```

### Use Voice Chat

```typescript
import { VoiceChat } from '@/components/voice/VoiceChat';

function VoiceInterface() {
  return (
    <VoiceChat
      sdk={sdk}
      voice="alloy"
      onTranscribe={(text) => console.log('Transcribed:', text)}
      onSpeak={(text) => console.log('Speaking:', text)}
    />
  );
}
```

### Use WebSocket Provider

```typescript
import { WebSocketProvider, useWebSocket } from '@/providers/WebSocketProvider';

function App() {
  return (
    <WebSocketProvider
      url="wss://api.zantara.com/ws"
      token="your-token"
      autoConnect={true}
    >
      <YourComponents />
    </WebSocketProvider>
  );
}

function YourComponent() {
  const { isConnected, subscribe } = useWebSocket();

  useEffect(() => {
    const unsubscribe = subscribe('USER_NOTIFICATIONS', (message) => {
      console.log('Notification:', message);
    });
    return unsubscribe;
  }, [subscribe]);

  return <div>Connected: {isConnected ? 'Yes' : 'No'}</div>;
}
```

### Use Pricing Widget

```typescript
import { DynamicPricingWidget } from '@/components/pricing/DynamicPricingWidget';

function PricingPage() {
  return (
    <DynamicPricingWidget
      sdk={sdk}
      onCalculate={(result) => console.log('Pricing:', result)}
    />
  );
}
```

## API Reference

### SDK Methods

#### Agentic RAG (Zantara AI)
- `queryAgenticRAG(request: AgenticRAGQueryRequest): Promise<AgenticRAGQueryResponse>`

#### Memory
- `getUserMemory(userId: string): Promise<UserMemory>`
- `addUserFact(userId: string, fact: string): Promise<{ success: boolean }>`
- `getCollectiveMemory(category?: string, limit?: number): Promise<CollectiveMemory[]>`
- `getEpisodicTimeline(request: EpisodicTimelineRequest): Promise<EpisodicEvent[]>`

#### Audio
- `transcribeAudio(request: TranscribeRequest): Promise<TranscribeResponse>`
- `generateSpeech(request: SpeechRequest): Promise<Blob>`

#### Journeys
- `createJourney(request: CreateJourneyRequest): Promise<ClientJourney>`
- `getJourney(journeyId: string): Promise<ClientJourney>`
- `getJourneyProgress(journeyId: string): Promise<JourneyProgress>`
- `completeStep(journeyId: string, stepId: string, notes?: string): Promise<{ success: boolean }>`

#### Compliance
- `getComplianceDeadlines(request?: ComplianceDeadlinesRequest): Promise<ComplianceItem[]>`
- `getComplianceAlerts(clientId?: string, status?: string): Promise<ComplianceAlert[]>`
- `acknowledgeAlert(alertId: string): Promise<{ success: boolean }>`

#### Pricing
- `calculatePricing(scenario: string, userLevel?: number): Promise<PricingResult>`

#### Team Analytics
- `getBurnoutSignals(userEmail?: string): Promise<BurnoutSignal[]>`
- `getTeamInsights(): Promise<TeamInsights>`

#### Knowledge Graph
- `addGraphEntity(entity: GraphEntity): Promise<{ id: string }>`
- `addGraphRelation(relation: GraphRelation): Promise<{ id: number }>`
- `getGraphNeighbors(entityId: string, relationType?: string): Promise<Array<...>>`
- `traverseGraph(startId: string, maxDepth?: number): Promise<GraphTraversalResult>`

#### Image Generation
- `generateImage(request: ImageGenerationRequest): Promise<ImageGenerationResponse>`

## React Hooks

### `useAgenticRAGStream(baseUrl, apiKey)`
The primary hook for streaming Zantara AI responses.
Returns:
- `stream(request)` - Start streaming query
- `stop()` - Stop streaming
- `reset()` - Reset state
- `tokens` - Accumulated response text
- `sources` - Source documents
- `isStreaming` - Streaming status
- `isComplete` - Completion status
- `error` - Error message

### `useWebSocket()`
Returns:
- `isConnected` - Connection status
- `connect()` - Connect to WebSocket
- `disconnect()` - Disconnect
- `sendMessage(message)` - Send message
- `subscribe(channel, callback)` - Subscribe to channel, returns unsubscribe function

## Components

### Memory Components
- `UserFactsDisplay` - Display and manage user profile facts
- `EpisodicTimeline` - Visualize user events over time
- `MemoryContext` - Combined memory view with tabs

### Journey Components
- `JourneyProgressTracker` - Complete journey visualization with step tracking

### Compliance Components
- `ComplianceCalendar` - Deadline calendar with alerts

### Voice Components
- `VoiceChat` - Speech-to-text and text-to-speech interface

### Pricing Components
- `DynamicPricingWidget` - Scenario-based pricing calculator

## Type Definitions

All types are exported from `@/lib/api/zantara-sdk/types`. Key types include:

- `AgenticRAGQueryRequest`, `AgenticRAGQueryResponse`
- `UserMemory`, `CollectiveMemory`, `EpisodicEvent`
- `ClientJourney`, `JourneyProgress`, `JourneyStep`
- `ComplianceItem`, `ComplianceAlert`
- `PricingResult`, `CostItem`
- `WebSocketMessage`, `WebSocketChannel`
- And many more...

## Examples

See the component files for complete implementation examples. All components are fully typed and ready to use.


