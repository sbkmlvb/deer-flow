import {
  GraduationCapIcon,
  ImageIcon,
  LightbulbIcon,
  MicroscopeIcon,
  PenLineIcon,
  ShapesIcon,
  VideoIcon,
  WandIcon,
} from "lucide-react";

import type { Translations } from "./types";

export const enUS: Translations = {
  locale: {
    localName: "English",
  },

  common: {
    home: "Home",
    settings: "Settings",
    delete: "Delete",
    rename: "Rename",
    share: "Share",
    openInNewWindow: "Open in new window",
    close: "Close",
    more: "More",
    search: "Search",
    download: "Download",
    thinking: "Thinking",
    artifacts: "Artifacts",
    public: "Public",
    custom: "Custom",
    notAvailableInDemoMode: "Not available in demo mode",
    loading: "Loading...",
    version: "Version",
    lastUpdated: "Last updated",
    code: "Code",
    preview: "Preview",
    cancel: "Cancel",
    save: "Save",
    saving: "Saving...",
    install: "Install",
    create: "Create",
    export: "Export",
    exportAsMarkdown: "Export as Markdown",
    exportAsJSON: "Export as JSON",
    exportSuccess: "Conversation exported",
  },

  welcome: {
    greeting: "Hello, again!",
    description:
      "Welcome to JRAiController, your professional stage lighting control assistant. I can help you manage lighting programs, edit sequences, configure DMX devices, and coordinate stage effects.",

    createYourOwnSkill: "Create Your Own Skill",
    createYourOwnSkillDescription:
      "Create your own skill to extend JRAiController's capabilities. With customized skills,\nyou can implement advanced features like automated lighting control and sequence generation.",
  },

  clipboard: {
    copyToClipboard: "Copy to clipboard",
    copiedToClipboard: "Copied to clipboard",
    failedToCopyToClipboard: "Failed to copy to clipboard",
    linkCopied: "Link copied to clipboard",
  },

  inputBox: {
    placeholder: "How can I assist you today?",
    createSkillPrompt:
      "We're going to build a new skill step by step with `skill-creator`. To start, what do you want this skill to do?",
    addAttachments: "Add attachments",
    mode: "Mode",
    flashMode: "Flash",
    flashModeDescription: "Fast and efficient, but may not be accurate",
    reasoningMode: "Reasoning",
    reasoningModeDescription:
      "Reasoning before action, balance between time and accuracy",
    proMode: "Pro",
    proModeDescription:
      "Reasoning, planning and executing, get more accurate results, may take more time",
    ultraMode: "Ultra",
    ultraModeDescription:
      "Pro mode with subagents to divide work; best for complex multi-step tasks",
    reasoningEffort: "Reasoning Effort",
    reasoningEffortMinimal: "Minimal",
    reasoningEffortMinimalDescription: "Retrieval + Direct Output",
    reasoningEffortLow: "Low",
    reasoningEffortLowDescription: "Simple Logic Check + Shallow Deduction",
    reasoningEffortMedium: "Medium",
    reasoningEffortMediumDescription:
      "Multi-layer Logic Analysis + Basic Verification",
    reasoningEffortHigh: "High",
    reasoningEffortHighDescription:
      "Full-dimensional Logic Deduction + Multi-path Verification + Backward Check",
    searchModels: "Search models...",
    surpriseMe: "Surprise",
    surpriseMePrompt: "Surprise me",
    followupLoading: "Generating follow-up questions...",
    followupConfirmTitle: "Send suggestion?",
    followupConfirmDescription:
      "You already have text in the input. Choose how to send it.",
    followupConfirmAppend: "Append & send",
    followupConfirmReplace: "Replace & send",
    suggestions: [
      {
        suggestion: "Lighting Program",
        prompt: "Help me create a lighting program about [topic]",
        icon: LightbulbIcon,
      },
      {
        suggestion: "Sequence Edit",
        prompt: "Create a sequence with [steps] lighting changes",
        icon: VideoIcon,
      },
      {
        suggestion: "Asset Management",
        prompt: "Organize my [type] assets",
        icon: ShapesIcon,
      },
      {
        suggestion: "Learn",
        prompt: "Teach me how to use [feature], create a tutorial",
        icon: GraduationCapIcon,
      },
    ],
    suggestionsCreate: [
      {
        suggestion: "Lighting Program",
        prompt: "Generate a lighting program about [topic]",
        icon: WandIcon,
      },
      {
        suggestion: "Edit Image",
        prompt: "Process a [type] stage background image",
        icon: ImageIcon,
      },
      {
        suggestion: "Video",
        prompt: "Generate a video about [topic]",
        icon: VideoIcon,
      },
      {
        type: "separator",
      },
      {
        suggestion: "Skill",
        prompt:
          "We're going to build a new skill step by step with `skill-creator`. To start, what do you want this skill to do?",
        icon: PenLineIcon,
      },
    ],
  },

  sidebar: {
    newChat: "New chat",
    chats: "Chats",
    recentChats: "Recent chats",
    demoChats: "Demo chats",
    agents: "Agents",
  },

  agents: {
    title: "Agents",
    description:
      "Create and manage custom agents with specialized prompts and capabilities.",
    newAgent: "New Agent",
    emptyTitle: "No custom agents yet",
    emptyDescription:
      "Create your first custom agent with a specialized system prompt.",
    chat: "Chat",
    delete: "Delete",
    deleteConfirm:
      "Are you sure you want to delete this agent? This action cannot be undone.",
    deleteSuccess: "Agent deleted",
    newChat: "New chat",
    createPageTitle: "Design your Agent",
    createPageSubtitle:
      "Describe the agent you want — I'll help you create it through conversation.",
    nameStepTitle: "Name your new Agent",
    nameStepHint:
      "Letters, digits, and hyphens only — stored lowercase (e.g. code-reviewer)",
    nameStepPlaceholder: "e.g. code-reviewer",
    nameStepContinue: "Continue",
    nameStepInvalidError:
      "Invalid name — use only letters, digits, and hyphens",
    nameStepAlreadyExistsError: "An agent with this name already exists",
    nameStepCheckError: "Could not verify name availability — please try again",
    nameStepBootstrapMessage:
      "The new custom agent name is {name}. Let's bootstrap it's **SOUL**.",
    agentCreated: "Agent created!",
    startChatting: "Start chatting",
    backToGallery: "Back to Gallery",
  },

  breadcrumb: {
    workspace: "Workspace",
    chats: "Chats",
  },

  workspace: {
    officialWebsite: "Official Website",
    githubTooltip: "View on GitHub",
    settingsAndMore: "Settings and more",
    visitGithub: "Visit GitHub",
    reportIssue: "Report Issue",
    contactUs: "Contact Us",
    about: "About",
  },

  conversation: {
    noMessages: "No messages yet",
    startConversation: "Start a conversation to see messages here",
  },

  chats: {
    searchChats: "Search chats",
  },

  pages: {
    appName: "JRAiController",
    chats: "Chats",
    newChat: "New chat",
    untitled: "Untitled",
  },

  toolCalls: {
    moreSteps: (count: number) => `${count} more step${count === 1 ? "" : "s"}`,
    lessSteps: "Less steps",
    executeCommand: "Execute command",
    presentFiles: "Present files",
    needYourHelp: "Need your help",
    useTool: (toolName: string) => `Use "${toolName}" tool`,
    searchFor: (query: string) => `Search for "${query}"`,
    searchForRelatedInfo: "Search for related information",
    searchForRelatedImages: "Search for related images",
    searchForRelatedImagesFor: (query: string) =>
      `Search for related images for "${query}"`,
    searchOnWebFor: (query: string) => `Search on the web for "${query}"`,
    viewWebPage: "View web page",
    listFolder: "List folder",
    readFile: "Read file",
    writeFile: "Write file",
    clickToViewContent: "Click to view file content",
    writeTodos: "Update to-do list",
    skillInstallTooltip: "Install skill and make it available to JRAiController",
  },

  uploads: {
    uploading: "Uploading...",
    uploadingFiles: "Uploading files, please wait...",
  },

  subtasks: {
    subtask: "Subtask",
    executing: (count: number) =>
      `Executing ${count === 1 ? "" : count + " "}subtask${count === 1 ? "" : "s in parallel"}`,
    in_progress: "Running subtask",
    completed: "Subtask completed",
    failed: "Subtask failed",
  },

  tokenUsage: {
    title: "Token Usage",
    input: "Input",
    output: "Output",
    total: "Total",
  },

  clarification: {
    step: (current: number, total: number) => `Step ${current}/${total}`,
    recommended: "Recommended",
    other: "Other...",
    customPlaceholder: "Enter your custom input...",
    back: "Back",
    skip: "Skip",
    confirm: "Confirm",
    submitting: "Submitting...",
    next: "Next",
    submitAll: "Submit All",
    optional: "Optional",
    enterText: "Enter text...",
    selectedCount: (count: number) => `${count} selected`,
    // Validation errors
    errorRequired: "This question is required. Please answer before continuing.",
    errorNoQuestion: "No question found.",
    errorSelectOne: "Please select at least one option.",
    errorCustomRequired: "Please enter your custom input.",
  },

  shortcuts: {
    searchActions: "Search actions...",
    noResults: "No results found.",
    actions: "Actions",
    keyboardShortcuts: "Keyboard Shortcuts",
    keyboardShortcutsDescription: "Navigate JRAiController faster with keyboard shortcuts.",
    openCommandPalette: "Open Command Palette",
    toggleSidebar: "Toggle Sidebar",
  },

  settings: {
    title: "Settings",
    description: "Adjust how JRAiController looks and behaves for you.",
    sections: {
      appearance: "Appearance",
      models: "Models",
      memory: "Memory",
      tools: "Tools",
      skills: "Skills",
      notification: "Notification",
      about: "About",
    },
    models: {
      title: "AI Model Configuration",
      description: "Configure AI model providers, API keys, and other parameters.",
      defaultModel: "Default Model",
      selectDefault: "Select the default model to use",
      models: "Model List",
      addModel: "Add Model",
      editModel: "Edit Model",
      name: "Name",
      displayName: "Display Name",
      provider: "Provider",
      model: "Model",
      baseUrl: "API Base URL",
      apiKey: "API Key",
      thinking: "Thinking",
      vision: "Vision",
      default: "Default",
      addDescription: "Add a new AI model configuration",
      editDescription: "Modify model configuration",
      loadError: "Failed to load models",
      saveError: "Failed to save configuration",
      deleteError: "Failed to delete model",
      addError: "Failed to add model",
      updateError: "Failed to update model",
      nameRequired: "Name and model are required",
      nameExists: "Model name already exists",
    },
    memory: {
      title: "Memory",
      description:
        "JRAiController automatically learns from your conversations in the background. These memories help JRAiController understand you better and deliver a more personalized experience.",
      empty: "No memory data to display.",
      rawJson: "Raw JSON",
      markdown: {
        overview: "Overview",
        userContext: "User context",
        work: "Work",
        personal: "Personal",
        topOfMind: "Top of mind",
        historyBackground: "History",
        recentMonths: "Recent months",
        earlierContext: "Earlier context",
        longTermBackground: "Long-term background",
        updatedAt: "Updated at",
        facts: "Facts",
        empty: "(empty)",
        table: {
          category: "Category",
          confidence: "Confidence",
          confidenceLevel: {
            veryHigh: "Very high",
            high: "High",
            normal: "Normal",
            unknown: "Unknown",
          },
          content: "Content",
          source: "Source",
          createdAt: "CreatedAt",
          view: "View",
        },
      },
    },
    appearance: {
      themeTitle: "Theme",
      themeDescription:
        "Choose how the interface follows your device or stays fixed.",
      system: "System",
      light: "Light",
      dark: "Dark",
      systemDescription: "Match the operating system preference automatically.",
      lightDescription: "Bright palette with higher contrast for daytime.",
      darkDescription: "Dim palette that reduces glare for focus.",
      languageTitle: "Language",
      languageDescription: "Switch between languages.",
    },
    tools: {
      title: "Tools",
      description: "Manage the configuration and enabled status of MCP tools.",
    },
    skills: {
      title: "Agent Skills",
      description:
        "Manage the configuration and enabled status of the agent skills.",
      createSkill: "Create skill",
      emptyTitle: "No agent skill yet",
      emptyDescription:
        "Put your agent skill folders under the `/skills/custom` folder under the root folder of JRAiController.",
      emptyButton: "Create Your First Skill",
    },
    notification: {
      title: "Notification",
      description:
        "JRAiController only sends a completion notification when the window is not active. This is especially useful for long-running tasks so you can switch to other work and get notified when done.",
      requestPermission: "Request notification permission",
      deniedHint:
        "Notification permission was denied. You can enable it in your browser's site settings to receive completion alerts.",
      testButton: "Send test notification",
      testTitle: "JRAiController",
      testBody: "This is a test notification.",
      notSupported: "Your browser does not support notifications.",
      disableNotification: "Disable notification",
    },
    acknowledge: {
      emptyTitle: "Acknowledgements",
      emptyDescription: "Credits and acknowledgements will show here.",
    },
  },
};