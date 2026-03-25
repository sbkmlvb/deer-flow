export function GET() {
  return Response.json({
    models: [
      {
        name: "gpt-4",
        display_name: "GPT-4",
        description: "OpenAI GPT-4 模型",
        use: "langchain_openai.ChatOpenAI",
        model: "gpt-4",
        supports_thinking: false,
        supports_vision: true,
      },
      {
        name: "gpt-4o",
        display_name: "GPT-4o",
        description: "OpenAI GPT-4o 模型",
        use: "langchain_openai.ChatOpenAI",
        model: "gpt-4o",
        supports_thinking: false,
        supports_vision: true,
      },
      {
        name: "claude-sonnet-4-20250514",
        display_name: "Claude Sonnet 4",
        description: "Anthropic Claude Sonnet 4 模型",
        use: "langchain_anthropic.ChatAnthropic",
        model: "claude-sonnet-4-20250514",
        supports_thinking: false,
        supports_vision: true,
      },
    ],
    default_model: "gpt-4",
  });
}
