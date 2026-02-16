/**
 * Chat Page - Refactored Modular Architecture
 *
 * Lightweight orchestrator that composes custom hooks and UI components.
 * Reduced from 1938 lines to ~250 lines by extracting logic into hooks.
 *
 * @module ChatPage
 */

"use client";

import { Loader2 } from "lucide-react";

// Custom Hooks
import { useChatPage } from "@/hooks/useChatPage";
import type { Message, AgentStep } from "@/types";

// Components
import { ChatHeader } from "@/components/chat/ChatHeader";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatMessageListVirtualized } from "@/components/chat/ChatMessageListVirtualized";
import { ChatInputBar } from "@/components/chat/ChatInputBar";
import { ImageGenModal } from "@/components/chat/ImageGenModal";
import { SearchDocsModal } from "@/components/search/SearchDocsModal";
import { Toast } from "@/components/chat/Toast";

/**
 * Chat Page Component - Modular Architecture
 *
 * This is a lightweight orchestrator that composes:
 * - Custom hooks for business logic (useChatPage)
 * - UI components for rendering
 *
 * Responsibilities:
 * - Layout and composition only
 * - No business logic (all in hooks)
 */
export default function ChatPage() {
  const {
    // State
    isInitialLoading,
    displayMessages,
    userName,
    userAvatar,
    showUserMenu,
    toast,
    isPending,
    currentStatus,
    streamingSteps,
    imageModalOpen,

    // Refs
    messagesEndRef,
    fileInputRef,

    // Hooks
    chatInput,
    sidebar,
    conversations,
    teamStatus,

    // Handlers
    handleSend,
    handleNewChat,
    handleConversationClick,
    handleDeleteConversation,
    handleAvatarChange,
    handleImageGenSubmit,
    toggleClock,
    showToast,
    setShowUserMenu,
    setToast,
    setImageModalOpen,
  } = useChatPage();

  // Loading state
  if (isInitialLoading) {
    return (
      <div className="flex h-screen bg-[#202020] text-white items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
          <p className="text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#202020] text-white">
      {/* Hidden file input for avatar upload */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleAvatarChange}
        accept="image/*"
        className="hidden"
      />

      {/* Toast Notification */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      {/* Sidebar */}
      <ChatSidebar
        isOpen={sidebar.sidebarOpen}
        onClose={sidebar.closeSidebar}
        onNewChat={handleNewChat}
        onConversationClick={handleConversationClick}
        onDeleteConversation={handleDeleteConversation}
        onSearchDocsOpen={sidebar.openSearchDocs}
        conversations={conversations.conversations}
        currentConversationId={conversations.currentConversationId}
        isLoading={conversations.isLoading}
      />

      {/* Search Docs Modal */}
      <SearchDocsModal
        open={sidebar.isSearchDocsOpen}
        onClose={sidebar.closeSearchDocs}
        onInsert={(text) => {
          chatInput.setInput(
            chatInput.input ? `${chatInput.input}\n${text}` : text,
          );
        }}
        initialQuery={chatInput.input}
      />

      {/* Image Generation Modal */}
      <ImageGenModal
        isOpen={imageModalOpen}
        onClose={() => setImageModalOpen(false)}
        onSubmit={handleImageGenSubmit}
      />

      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header */}
        <ChatHeader
          isSidebarOpen={sidebar.sidebarOpen}
          onToggleSidebar={sidebar.toggleSidebar}
          isClockIn={teamStatus.isClockIn}
          isClockLoading={teamStatus.isLoading}
          onToggleClock={toggleClock}
          messagesCount={displayMessages.length}
          isWsConnected={true}
          userName={userName}
          userAvatar={userAvatar}
          showUserMenu={showUserMenu}
          onToggleUserMenu={() => setShowUserMenu(!showUserMenu)}
          userMenuRef={fileInputRef}
          avatarInputRef={fileInputRef}
          onAvatarUpload={handleAvatarChange}
          onShowToast={showToast}
        />

        {/* Messages Area */}
        <ChatMessageListVirtualized
          messages={displayMessages.map(
            (m): Message => ({
              id: m.id,
              role: m.role,
              content: m.content,
              timestamp: m.timestamp,
              sources: m.sources,
              imageUrl: m.imageUrl,
              steps: m.steps
                ? (m.steps.map((step) => ({
                    type: step.type as AgentStep["type"],
                    data: step.data,
                    timestamp: step.timestamp,
                  })) as AgentStep[])
                : undefined,
              currentStatus:
                m.isPending || m.isStreaming ? currentStatus : undefined,
              verification_score: undefined,
              metadata: m.metadata,
            }),
          )}
          isLoading={isPending}
          thinkingElapsedTime={0}
          userAvatar={userAvatar}
          messagesEndRef={messagesEndRef}
          onFollowUpClick={(question) => {
            chatInput.setInput(question);
            setTimeout(() => handleSend(), 10);
          }}
          onSetInput={chatInput.setInput}
          onOpenSearchDocs={sidebar.openSearchDocs}
        />

        {/* Input Bar */}
        <ChatInputBar
          input={chatInput.input}
          setInput={chatInput.setInput}
          isLoading={isPending}
          showImagePrompt={imageModalOpen}
          setShowImagePrompt={setImageModalOpen}
          onSend={handleSend}
          onImageGenerate={() => setImageModalOpen(true)}
          showAttachMenu={false}
          setShowAttachMenu={() => {}}
          attachMenuRef={chatInput.imageInputRef}
          fileInputRef={chatInput.imageInputRef}
          onFileChange={async (e) => {
            chatInput.handleImageAttach(e);
          }}
          isRecording={false}
          recordingTime={0}
          onStartRecording={() => {}}
          onStopRecording={() => {}}
          onToggleRecording={() => {
            showToast("Voice recording temporarily disabled.", "error");
          }}
        />
      </main>
    </div>
  );
}
