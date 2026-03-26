"""Clarification tool for requesting user input with interactive UI."""

from typing import Annotated, Any, Literal

from langchain.tools import tool


@tool("ask_clarification", parse_docstring=True, return_direct=True)
def ask_clarification_tool(
    questions: Annotated[
        list[dict[str, Any]],
        "List of questions to ask. Each question is a dict with required keys: 'id', 'question', 'type'. For choice types, include 'options' array. To allow users to enter custom answers not in the options, add {'label': '其他...', 'value': '__custom__'} to the options array.",
    ],
    title: str | None = None,
    context: str | None = None,
) -> str:
    """Ask the user multiple questions in a wizard-style interface.

    Use this tool when you need user input to proceed. All questions will be presented
    in a step-by-step wizard UI where users can navigate between questions.

    ## Question Types

    1. **single_choice**: User selects ONE option from a list
       - Include 'options' array with {label, description?, value?, recommended?} objects
       - Add {'label': '其他...', 'value': '__custom__'} to allow custom input

    2. **multiple_choice**: User can select MULTIPLE options
       - Include 'options' array with {label, description?, value?, recommended?} objects
       - Add {'label': '其他...', 'value': '__custom__'} to allow custom input

    3. **text_input**: User types free-form text
       - Use 'placeholder' for input hint
       - Use 'default_value' for pre-filled text

    4. **confirmation**: Yes/No confirmation
       - Include 'options' with yes/no choices

    ## Option Structure

    Each option in 'options' array should be:
    ```json
    {
      "label": "显示文本",
      "description": "可选的描述说明",
      "value": "选项值（可选，默认使用label）",
      "recommended": true  // 可选，标记为推荐
    }
    ```

    To allow custom user input, add this special option:
    ```json
    {"label": "其他...", "value": "__custom__"}
    ```

    ## Example

    ```json
    {
        "title": "文件处理配置",
        "context": "请配置以下处理选项",
        "questions": [
            {
                "id": "processing_mode",
                "question": "请选择处理模式",
                "type": "single_choice",
                "options": [
                    {"label": "快速模式", "description": "使用默认设置", "recommended": true},
                    {"label": "详细模式", "description": "自定义参数"},
                    {"label": "其他...", "value": "__custom__"}
                ]
            },
            {
                "id": "file_types",
                "question": "选择文件类型（可多选）",
                "type": "multiple_choice",
                "options": [
                    {"label": "图片"},
                    {"label": "文档"},
                    {"label": "其他...", "value": "__custom__"}
                ]
            },
            {
                "id": "output_name",
                "question": "请输入输出文件名",
                "type": "text_input",
                "placeholder": "例如: result.txt"
            }
        ]
    }
    ```

    Args:
        questions: List of question objects. Each MUST have 'id', 'question', 'type'.
            For choice types, include 'options' array. Add {'label': '其他...', 'value': '__custom__'} to allow custom input.
        title: Optional title shown at the top of the wizard.
        context: Optional description shown below the title.

    Returns:
        User's responses will be sent back as a JSON message with structure:
        {"title": "...", "responses": [{"question_id": "...", "question": "...", "answer": "..."}]}
    """
    # This is a placeholder implementation
    # The actual logic is handled by ClarificationMiddleware which intercepts this tool call
    # and interrupts execution to present the questions to the user
    return "Clarification request processed by middleware"
