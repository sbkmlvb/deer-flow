"use client";

import {
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CircleIcon,
  ListChecksIcon,
  PencilIcon,
  AlertCircleIcon,
  AlertTriangleIcon,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/core/i18n/hooks";
import { cn } from "@/lib/utils";

/**
 * Question types
 */
type QuestionType = "single_choice" | "multiple_choice" | "text_input" | "confirmation";

/**
 * Structured option from backend
 */
interface ClarificationOption {
  label: string;
  description?: string | null;
  value: string;
  recommended?: boolean;
}

/**
 * Single question structure
 */
interface ClarificationQuestion {
  id: string;
  question: string;
  type: QuestionType;
  options: ClarificationOption[];
  allow_custom?: boolean;
  placeholder?: string | null;
  default_value?: string | string[] | null;
  required?: boolean;
}

/**
 * Parsed clarification data from backend
 */
interface ClarificationData {
  title?: string | null;
  context?: string | null;
  questions: ClarificationQuestion[];
  total_questions: number;
}

/**
 * User responses for all questions
 */
type QuestionResponses = Record<string, string | string[]>;

/**
 * Custom input state for each question
 */
type CustomInputs = Record<string, string>;

/**
 * Which questions have "Other..." selected
 */
type CustomSelected = Record<string, boolean>;

/**
 * Parse clarification data from message content
 */
export function parseClarificationData(content: string): ClarificationData | null {
  // Match the JSON block embedded by backend
  const match = content.match(/<!--CLARIFICATION_DATA\n([\s\S]*?)\n-->/);
  if (!match || !match[1]) {
    return null;
  }

  try {
    return JSON.parse(match[1]) as ClarificationData;
  } catch (e) {
    console.error("[ClarificationCard] Failed to parse clarification data:", e);
    return null;
  }
}

/**
 * Check if a message is a clarification message
 */
export function isClarificationMessage(content: string): boolean {
  return content.includes("<!--CLARIFICATION_DATA");
}

/**
 * Type icons mapping
 */
const TYPE_ICONS: Record<QuestionType, typeof CircleIcon> = {
  single_choice: CircleIcon,
  multiple_choice: ListChecksIcon,
  text_input: PencilIcon,
  confirmation: AlertCircleIcon,
};

const TYPE_COLORS: Record<QuestionType, string> = {
  single_choice: "text-blue-500",
  multiple_choice: "text-purple-500",
  text_input: "text-green-500",
  confirmation: "text-orange-500",
};

/**
 * Special value for custom input
 */
const CUSTOM_VALUE = "__custom__";

interface ClarificationCardProps {
  content: string;
  onRespond?: (response: string) => void;
  className?: string;
  isLoading?: boolean;
}

export function ClarificationCard({
  content,
  onRespond,
  className,
  isLoading = false,
}: ClarificationCardProps) {
  const { t } = useI18n();
  const data = useMemo(() => parseClarificationData(content), [content]);

  // Current question index (0-based)
  const [currentStep, setCurrentStep] = useState(0);

  // Validation error state
  const [validationError, setValidationError] = useState<string | null>(null);

  // Store responses for all questions
  const [responses, setResponses] = useState<QuestionResponses>(() => {
    if (!data?.questions) return {};
    const initial: QuestionResponses = {};
    for (const q of data.questions) {
      if (q.default_value !== undefined && q.default_value !== null) {
        initial[q.id] = q.default_value;
      }
    }
    return initial;
  });

  // Store custom input values
  const [customInputs, setCustomInputs] = useState<CustomInputs>({});

  // Track which questions have "Other..." selected
  const [customSelected, setCustomSelected] = useState<CustomSelected>({});

  // Get current question
  const currentQuestion = data?.questions[currentStep];
  const totalSteps = data?.total_questions ?? 1;
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === totalSteps - 1;

  // Check if current question allows custom input
  // Either allow_custom is true, or there's an option with value="__custom__"
  const hasCustomOption = currentQuestion?.options?.some(
    (opt) => opt.value === CUSTOM_VALUE
  ) ?? false;
  const allowCustom = (currentQuestion?.allow_custom ?? false) || hasCustomOption;

  // Handle single choice selection
  const handleSingleChoice = useCallback((questionId: string, value: string) => {
    setResponses((prev) => ({ ...prev, [questionId]: value }));
    setValidationError(null);  // 清除错误
    // If selecting a non-custom option, clear custom selected
    if (value !== CUSTOM_VALUE) {
      setCustomSelected((prev) => ({ ...prev, [questionId]: false }));
    }
  }, []);

  // Handle custom option click
  const handleCustomClick = useCallback((questionId: string) => {
    setCustomSelected((prev) => ({ ...prev, [questionId]: true }));
    setResponses((prev) => ({ ...prev, [questionId]: CUSTOM_VALUE }));
    setValidationError(null);
  }, []);

  // Handle multiple choice selection (toggle)
  const handleMultipleChoice = useCallback((questionId: string, value: string) => {
    setResponses((prev) => {
      const current = prev[questionId];
      const currentArray = Array.isArray(current) ? current : [];
      const exists = currentArray.includes(value);
      return {
        ...prev,
        [questionId]: exists
          ? currentArray.filter((v) => v !== value)
          : [...currentArray, value],
      };
    });
    setValidationError(null);
  }, []);

  // Handle custom input change
  const handleCustomInputChange = useCallback((questionId: string, value: string) => {
    setCustomInputs((prev) => ({ ...prev, [questionId]: value }));
    setValidationError(null);
  }, []);

  // Handle text input
  const handleTextInput = useCallback((questionId: string, value: string) => {
    setResponses((prev) => ({ ...prev, [questionId]: value }));
    setValidationError(null);
  }, []);

  // Check if current question is answered
  const isCurrentQuestionAnswered = useCallback((): { answered: boolean; error?: string } => {
    if (!currentQuestion) return { answered: false, error: t.clarification.errorNoQuestion };
    if (currentQuestion.required === false) return { answered: true };

    const response = responses[currentQuestion.id];

    // For text_input type, check if there's any content
    if (currentQuestion.type === "text_input") {
      const hasContent = typeof response === "string" && response.trim().length > 0;
      return {
        answered: hasContent,
        error: hasContent ? undefined : t.clarification.errorRequired,
      };
    }

    // For choice types
    if (response === undefined || response === null) {
      return { answered: false, error: t.clarification.errorRequired };
    }
    if (typeof response === "string") {
      // For custom input, check if custom value is filled
      if (response === CUSTOM_VALUE) {
        const customValue = customInputs[currentQuestion.id];
        const hasContent = !!customValue?.trim();
        return {
          answered: hasContent,
          error: hasContent ? undefined : t.clarification.errorCustomRequired,
        };
      }
      const hasContent = response.trim().length > 0;
      return {
        answered: hasContent,
        error: hasContent ? undefined : t.clarification.errorRequired,
      };
    }
    if (Array.isArray(response)) {
      const hasContent = response.length > 0;
      return {
        answered: hasContent,
        error: hasContent ? undefined : t.clarification.errorSelectOne,
      };
    }
    return { answered: false, error: t.clarification.errorRequired };
  }, [currentQuestion, responses, customInputs, t]);

  // Get the actual answer for a question (resolving custom inputs)
  const getActualAnswer = useCallback(
    (question: ClarificationQuestion): string | string[] | null => {
      const response = responses[question.id];
      if (response === undefined || response === null) return null;

      // Handle custom input for single choice
      if (question.type === "single_choice" && response === CUSTOM_VALUE) {
        return customInputs[question.id]?.trim() || null;
      }

      // Handle custom input for multiple choice
      if (question.type === "multiple_choice" && Array.isArray(response)) {
        return response.map((v) =>
          v === CUSTOM_VALUE ? customInputs[question.id]?.trim() || v : v
        );
      }

      return response;
    },
    [responses, customInputs]
  );

  // Navigation handlers
  const handleBack = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
      setValidationError(null);
    }
  }, [currentStep]);

  // Validate and move to next step
  const handleNextWithValidation = useCallback(() => {
    const { answered, error } = isCurrentQuestionAnswered();
    if (!answered) {
      setValidationError(error || t.clarification.errorRequired);
      return;
    }
    setValidationError(null);
    if (currentStep < totalSteps - 1) {
      setCurrentStep((prev) => prev + 1);
    }
  }, [currentStep, totalSteps, isCurrentQuestionAnswered, t]);

  // Validate and submit
  const handleSubmitWithValidation = useCallback(() => {
    const { answered, error } = isCurrentQuestionAnswered();
    if (!answered) {
      setValidationError(error || t.clarification.errorRequired);
      return;
    }
    setValidationError(null);

    if (!data) return;

    // Build response object
    const responsePayload = {
      title: data.title,
      responses: data.questions.map((q) => ({
        question_id: q.id,
        question: q.question,
        answer: getActualAnswer(q),
      })),
    };

    // Send as JSON string
    onRespond?.(JSON.stringify(responsePayload, null, 2));
  }, [data, isCurrentQuestionAnswered, getActualAnswer, onRespond, t]);

  // Skip this question (only for non-required)
  const handleSkip = useCallback(() => {
    setValidationError(null);
    if (isLastStep) {
      handleSubmitWithValidation();
    } else {
      setCurrentStep((prev) => prev + 1);
    }
  }, [isLastStep, handleSubmitWithValidation]);

  // Fallback rendering if data parsing fails
  if (!data || !currentQuestion) {
    return (
      <Card className={cn("max-w-xl", className)}>
        <CardContent className="whitespace-pre-wrap p-4">{content}</CardContent>
      </Card>
    );
  }

  const Icon = TYPE_ICONS[currentQuestion.type] || CircleIcon;
  const iconColor = TYPE_COLORS[currentQuestion.type] || "text-gray-500";
  const currentResponse = responses[currentQuestion.id];

  return (
    <Card className={cn("max-w-xl overflow-hidden", className)}>
      {/* Header with progress */}
      <CardHeader className="pb-3">
        {/* Title */}
        {data.title && (
          <div className="mb-2 text-lg font-semibold">{data.title}</div>
        )}

        {/* Progress bar */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{t.clarification.step(currentStep + 1, totalSteps)}</span>
          <div className="flex-1">
            <div className="bg-muted h-1.5 w-full overflow-hidden rounded-full">
              <div
                className="bg-primary h-full transition-all"
                style={{
                  width: `${((currentStep + 1) / totalSteps) * 100}%`,
                }}
              />
            </div>
          </div>
        </div>

        {/* Context */}
        {data.context && currentStep === 0 && (
          <p className="text-sm text-muted-foreground">{data.context}</p>
        )}
      </CardHeader>

      {/* Question content */}
      <CardContent className="space-y-3 pb-3">
        {/* Question title */}
        <CardTitle className="flex items-start gap-2 text-base font-medium">
          <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", iconColor)} />
          <span className="flex-1">{currentQuestion.question}</span>
          {!currentQuestion.required && (
            <span className="text-xs text-muted-foreground">
              ({t.clarification.optional})
            </span>
          )}
        </CardTitle>

        {/* Validation error alert */}
        {validationError && (
          <Alert variant="destructive" className="py-2">
            <AlertTriangleIcon className="h-4 w-4" />
            <AlertDescription>{validationError}</AlertDescription>
          </Alert>
        )}

        {/* Single choice options */}
        {currentQuestion.type === "single_choice" && (
          <div className="space-y-2">
            {currentQuestion.options
              .filter((option) => option.value !== CUSTOM_VALUE)  // 过滤掉 __custom__ 选项
              .map((option) => {
                const isSelected = currentResponse === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => handleSingleChoice(currentQuestion.id, option.value)}
                    disabled={isLoading}
                    className={cn(
                      "w-full rounded-lg border p-3 text-left transition-all",
                      "hover:border-primary/50 hover:bg-accent/50",
                      "focus:outline-none focus:ring-2 focus:ring-primary/50",
                      isSelected
                        ? "border-primary bg-primary/10"
                        : "border-border",
                      isLoading && "cursor-not-allowed opacity-50",
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <div
                        className={cn(
                          "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border",
                          isSelected
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-muted-foreground",
                        )}
                      >
                        {isSelected && <CheckIcon className="h-3 w-3" />}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{option.label}</span>
                          {option.recommended && (
                            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
                              {t.clarification.recommended}
                            </span>
                          )}
                        </div>
                        {option.description && (
                          <p className="mt-0.5 text-sm text-muted-foreground">
                            {option.description}
                          </p>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}

            {/* Other option for single choice - shown when allowCustom is true OR there's a __custom__ option */}
            {allowCustom && (
              <>
                <button
                  type="button"
                  onClick={() => handleCustomClick(currentQuestion.id)}
                  disabled={isLoading}
                  className={cn(
                    "w-full rounded-lg border border-dashed p-3 text-left transition-all",
                    "hover:border-primary/50 hover:bg-accent/50",
                    "focus:outline-none focus:ring-2 focus:ring-primary/50",
                    customSelected[currentQuestion.id]
                      ? "border-primary bg-primary/10"
                      : "border-border",
                    isLoading && "cursor-not-allowed opacity-50",
                  )}
                >
                  <div className="flex items-center gap-2">
                    <div
                      className={cn(
                        "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border",
                        customSelected[currentQuestion.id]
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-muted-foreground",
                      )}
                    >
                      {customSelected[currentQuestion.id] && (
                        <CheckIcon className="h-3 w-3" />
                      )}
                    </div>
                    <span className="text-muted-foreground">
                      {t.clarification.other}
                    </span>
                  </div>
                </button>

                {/* Custom input field */}
                {customSelected[currentQuestion.id] && (
                  <Textarea
                    value={customInputs[currentQuestion.id] ?? ""}
                    onChange={(e) =>
                      handleCustomInputChange(currentQuestion.id, e.target.value)
                    }
                    placeholder={t.clarification.customPlaceholder}
                    className="mt-2 min-h-[60px]"
                    disabled={isLoading}
                    autoFocus
                  />
                )}
              </>
            )}
          </div>
        )}

        {/* Multiple choice options */}
        {currentQuestion.type === "multiple_choice" && (
          <div className="space-y-2">
            {currentQuestion.options
              .filter((option) => option.value !== CUSTOM_VALUE)  // 过滤掉 __custom__ 选项
              .map((option) => {
                const selectedArray = Array.isArray(currentResponse)
                  ? currentResponse
                  : [];
                const isSelected = selectedArray.includes(option.value);
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() =>
                      handleMultipleChoice(currentQuestion.id, option.value)
                    }
                    disabled={isLoading}
                    className={cn(
                      "w-full rounded-lg border p-3 text-left transition-all",
                      "hover:border-primary/50 hover:bg-accent/50",
                      "focus:outline-none focus:ring-2 focus:ring-primary/50",
                      isSelected
                        ? "border-primary bg-primary/10"
                        : "border-border",
                      isLoading && "cursor-not-allowed opacity-50",
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <div
                        className={cn(
                          "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                          isSelected
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-muted-foreground",
                        )}
                      >
                        {isSelected && <CheckIcon className="h-3 w-3" />}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{option.label}</span>
                          {option.recommended && (
                            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
                              {t.clarification.recommended}
                            </span>
                          )}
                        </div>
                        {option.description && (
                          <p className="mt-0.5 text-sm text-muted-foreground">
                            {option.description}
                          </p>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}

            {/* Other option for multiple choice */}
            {allowCustom && (
              <>
                <button
                  type="button"
                  onClick={() => {
                    handleMultipleChoice(currentQuestion.id, CUSTOM_VALUE);
                  }}
                  disabled={isLoading}
                  className={cn(
                    "w-full rounded-lg border border-dashed p-3 text-left transition-all",
                    "hover:border-primary/50 hover:bg-accent/50",
                    "focus:outline-none focus:ring-2 focus:ring-primary/50",
                    Array.isArray(currentResponse) &&
                      currentResponse.includes(CUSTOM_VALUE)
                      ? "border-primary bg-primary/10"
                      : "border-border",
                    isLoading && "cursor-not-allowed opacity-50",
                  )}
                >
                  <div className="flex items-center gap-2">
                    <div
                      className={cn(
                        "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                        Array.isArray(currentResponse) &&
                          currentResponse.includes(CUSTOM_VALUE)
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-muted-foreground",
                      )}
                    >
                      {Array.isArray(currentResponse) &&
                        currentResponse.includes(CUSTOM_VALUE) && (
                          <CheckIcon className="h-3 w-3" />
                        )}
                    </div>
                    <span className="text-muted-foreground">
                      {t.clarification.other}
                    </span>
                  </div>
                </button>

                {/* Custom input field for multiple choice */}
                {Array.isArray(currentResponse) &&
                  currentResponse.includes(CUSTOM_VALUE) && (
                    <Textarea
                      value={customInputs[currentQuestion.id] ?? ""}
                      onChange={(e) =>
                        handleCustomInputChange(currentQuestion.id, e.target.value)
                      }
                      placeholder={t.clarification.customPlaceholder}
                      className="mt-2 min-h-[60px]"
                      disabled={isLoading}
                      autoFocus
                    />
                  )}
              </>
            )}

            {Array.isArray(currentResponse) && currentResponse.length > 0 && (
              <p className="text-xs text-muted-foreground">
                {t.clarification.selectedCount(currentResponse.length)}
              </p>
            )}
          </div>
        )}

        {/* Text input */}
        {currentQuestion.type === "text_input" && (
          <div className="space-y-2">
            <Textarea
              value={typeof currentResponse === "string" ? currentResponse : ""}
              onChange={(e) => handleTextInput(currentQuestion.id, e.target.value)}
              placeholder={currentQuestion.placeholder ?? t.clarification.enterText}
              className="min-h-[80px]"
              disabled={isLoading}
            />
          </div>
        )}

        {/* Confirmation */}
        {currentQuestion.type === "confirmation" && (
          <div className="flex gap-3">
            {currentQuestion.options.map((option) => {
              const isSelected = currentResponse === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() =>
                    handleSingleChoice(currentQuestion.id, option.value)
                  }
                  disabled={isLoading}
                  className={cn(
                    "flex-1 rounded-lg border p-4 text-center transition-all",
                    "hover:border-primary/50 hover:bg-accent/50",
                    "focus:outline-none focus:ring-2 focus:ring-primary/50",
                    isSelected
                      ? "border-primary bg-primary/10"
                      : "border-border",
                    (option.value === "yes" || option.label.includes("确认")) &&
                      "text-primary",
                    !(
                      option.value === "yes" ||
                      option.label.includes("确认")
                    ) && "text-muted-foreground",
                    isLoading && "cursor-not-allowed opacity-50",
                  )}
                >
                  <span className="font-medium">{option.label}</span>
                </button>
              );
            })}
          </div>
        )}
      </CardContent>

      {/* Footer with navigation */}
      <CardFooter className="flex items-center justify-between border-t pt-3">
        <div className="flex items-center gap-2">
          {!isFirstStep && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleBack}
              disabled={isLoading}
            >
              <ChevronLeftIcon className="h-4 w-4" />
              {t.clarification.back}
            </Button>
          )}
          {!currentQuestion.required && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleSkip}
              disabled={isLoading}
            >
              {t.clarification.skip}
            </Button>
          )}
        </div>

        <div className="flex items-center gap-2">
          {isLastStep ? (
            <Button
              size="sm"
              onClick={handleSubmitWithValidation}
              disabled={isLoading}
            >
              {isLoading ? t.clarification.submitting : t.clarification.submitAll}
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={handleNextWithValidation}
              disabled={isLoading}
            >
              {t.clarification.next}
              <ChevronRightIcon className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardFooter>
    </Card>
  );
}
