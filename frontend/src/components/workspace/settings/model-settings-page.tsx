"use client";

import { useEffect, useState } from "react";
import { SettingsSection } from "./settings-section";
import { useI18n } from "@/core/i18n/hooks";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { PlusIcon, TrashIcon, PencilIcon } from "lucide-react";

interface ModelConfig {
  name: string;
  display_name?: string;
  description?: string;
  use: string;
  model: string;
  api_key?: string;
  base_url?: string;
  supports_thinking?: boolean;
  supports_vision?: boolean;
}

interface ModelsResponse {
  models: ModelConfig[];
  default_model: string;
}

const MODEL_PROVIDERS = [
  { value: "langchain_openai.ChatOpenAI", label: "OpenAI" },
  { value: "langchain_openai.ChatAzureOpenAI", label: "Azure OpenAI" },
  { value: "langchain_anthropic.ChatAnthropic", label: "Anthropic" },
  { value: "langchain_google_genai.ChatGoogleGenerativeAI", label: "Google Gemini" },
  { value: "langchain_mistralai.chat_integration.MistralAI", label: "Mistral AI" },
];

export function ModelSettingsPage() {
  const { t } = useI18n();
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [defaultModel, setDefaultModel] = useState<string>("gpt-4");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingModel, setEditingModel] = useState<ModelConfig | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [newModel, setNewModel] = useState<Partial<ModelConfig>>({
    use: "langchain_openai.ChatOpenAI",
    supports_thinking: false,
    supports_vision: false,
  });

  const fetchModels = async () => {
    try {
      setIsLoading(true);
      const response = await fetch("/api/models/config");
      if (response.ok) {
        const data: ModelsResponse = await response.json();
        setModels(data.models || []);
        setDefaultModel(data.default_model || "gpt-4");
      }
    } catch (err) {
      setError("Failed to load models");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchModels();
  }, []);

  const handleSave = async () => {
    try {
      setIsSaving(true);
      const response = await fetch("/api/models/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ models, default_model: defaultModel }),
      });
      if (!response.ok) {
        throw new Error("Failed to save");
      }
      await fetchModels();
    } catch (err) {
      setError("Failed to save configuration");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteModel = async (name: string) => {
    try {
      const response = await fetch(`/api/models/${name}`, {
        method: "DELETE",
      });
      if (response.ok) {
        setModels(models.filter((m) => m.name !== name));
      }
    } catch (err) {
      setError("Failed to delete model");
    }
  };

  const handleAddModel = async () => {
    if (!newModel.name || !newModel.model) {
      setError("Name and model are required");
      return;
    }

    try {
      const response = await fetch("/api/models/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newModel),
      });
      if (response.ok) {
        setIsAddDialogOpen(false);
        setNewModel({
          use: "langchain_openai.ChatOpenAI",
          supports_thinking: false,
          supports_vision: false,
        });
        await fetchModels();
      }
    } catch (err) {
      setError("Failed to add model");
    }
  };

  const handleUpdateModel = async () => {
    if (!editingModel) return;

    try {
      const response = await fetch(`/api/models/${editingModel.name}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(editingModel),
      });
      if (response.ok) {
        setIsDialogOpen(false);
        setEditingModel(null);
        await fetchModels();
      }
    } catch (err) {
      setError("Failed to update model");
    }
  };

  if (isLoading) {
    return (
      <SettingsSection title={t.settings.models?.title || "模型设置"} description={t.settings.models?.description || "配置 AI 模型提供商"}>
        <div className="text-muted-foreground text-sm">{t.common?.loading || "加载中..."}</div>
      </SettingsSection>
    );
  }

  return (
    <SettingsSection title={t.settings.models?.title || "模型设置"} description={t.settings.models?.description || "配置 AI 模型提供商"}>
      <div className="space-y-6">
        {error && (
          <div className="rounded-md bg-destructive/10 p-3 text-destructive text-sm">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-medium">{t.settings.models?.defaultModel || "默认模型"}</h3>
              <p className="text-muted-foreground text-sm">{t.settings.models?.selectDefault || "选择默认使用的模型"}</p>
            </div>
            <Select value={defaultModel} onValueChange={setDefaultModel}>
              <SelectTrigger className="w-[200px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {models.map((model) => (
                  <SelectItem key={model.name} value={model.name}>
                    {model.display_name || model.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-medium">{t.settings.models?.models || "模型列表"}</h3>
            <Button onClick={() => setIsAddDialogOpen(true)} size="sm">
              <PlusIcon className="mr-2 h-4 w-4" />
              {t.settings.models?.addModel || "添加模型"}
            </Button>
          </div>

          <div className="space-y-3">
            {models.map((model) => (
              <div
                key={model.name}
                className="flex items-center justify-between rounded-lg border p-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{model.display_name || model.name}</span>
                    {model.name === defaultModel && (
                      <Badge variant="secondary">{t.settings.models?.default || "默认"}</Badge>
                    )}
                    {model.supports_thinking && (
                      <Badge variant="outline">{t.settings.models?.thinking || "思考"}</Badge>
                    )}
                    {model.supports_vision && (
                      <Badge variant="outline">{t.settings.models?.vision || "视觉"}</Badge>
                    )}
                  </div>
                  <p className="text-muted-foreground text-sm">{model.description || model.model}</p>
                  <p className="text-muted-foreground text-xs">{model.use}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      setEditingModel(model);
                      setIsDialogOpen(true);
                    }}
                  >
                    <PencilIcon className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDeleteModel(model.name)}
                    disabled={models.length <= 1}
                  >
                    <TrashIcon className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex justify-end">
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? (t.common?.saving || "保存中...") : (t.common?.save || "保存")}
          </Button>
        </div>
      </div>

      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>{t.settings.models?.addModel || "添加模型"}</DialogTitle>
            <DialogDescription>{t.settings.models?.addDescription || "添加新的 AI 模型配置"}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">{t.settings.models?.name || "名称"}</Label>
              <Input
                id="name"
                value={newModel.name || ""}
                onChange={(e) => setNewModel({ ...newModel, name: e.target.value })}
                placeholder="e.g. gpt-4"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="display_name">{t.settings.models?.displayName || "显示名称"}</Label>
              <Input
                id="display_name"
                value={newModel.display_name || ""}
                onChange={(e) => setNewModel({ ...newModel, display_name: e.target.value })}
                placeholder="e.g. GPT-4"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="provider">{t.settings.models?.provider || "提供商"}</Label>
              <Select
                value={newModel.use || "langchain_openai.ChatOpenAI"}
                onValueChange={(value) => setNewModel({ ...newModel, use: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MODEL_PROVIDERS.map((provider) => (
                    <SelectItem key={provider.value} value={provider.value}>
                      {provider.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="model">{t.settings.models?.model || "模型"}</Label>
              <Input
                id="model"
                value={newModel.model || ""}
                onChange={(e) => setNewModel({ ...newModel, model: e.target.value })}
                placeholder="e.g. gpt-4"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="base_url">{t.settings.models?.baseUrl || "API Base URL"}</Label>
              <Input
                id="base_url"
                value={newModel.base_url || ""}
                onChange={(e) => setNewModel({ ...newModel, base_url: e.target.value })}
                placeholder="https://api.openai.com/v1 (可选)"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="api_key">{t.settings.models?.apiKey || "API Key"}</Label>
              <Input
                id="api_key"
                type="password"
                value={newModel.api_key || ""}
                onChange={(e) => setNewModel({ ...newModel, api_key: e.target.value })}
                placeholder="sk-... (可选)"
              />
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Switch
                  id="supports_thinking"
                  checked={newModel.supports_thinking || false}
                  onCheckedChange={(checked) =>
                    setNewModel({ ...newModel, supports_thinking: checked })
                  }
                />
                <Label htmlFor="supports_thinking">{t.settings.models?.thinking || "支持思考"}</Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  id="supports_vision"
                  checked={newModel.supports_vision || false}
                  onCheckedChange={(checked) =>
                    setNewModel({ ...newModel, supports_vision: checked })
                  }
                />
                <Label htmlFor="supports_vision">{t.settings.models?.vision || "支持视觉"}</Label>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
              {t.common?.cancel || "取消"}
            </Button>
            <Button onClick={handleAddModel}>{t.settings.models?.addModel || "添加"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>{t.settings.models?.editModel || "编辑模型"}</DialogTitle>
            <DialogDescription>{t.settings.models?.editDescription || "修改模型配置"}</DialogDescription>
          </DialogHeader>
          {editingModel && (
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="edit_name">{t.settings.models?.name || "名称"}</Label>
                <Input id="edit_name" value={editingModel.name} disabled />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit_display_name">{t.settings.models?.displayName || "显示名称"}</Label>
                <Input
                  id="edit_display_name"
                  value={editingModel.display_name || ""}
                  onChange={(e) =>
                    setEditingModel({ ...editingModel, display_name: e.target.value })
                  }
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit_base_url">{t.settings.models?.baseUrl || "API Base URL"}</Label>
                <Input
                  id="edit_base_url"
                  value={editingModel.base_url || ""}
                  onChange={(e) =>
                    setEditingModel({ ...editingModel, base_url: e.target.value })
                  }
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit_api_key">{t.settings.models?.apiKey || "API Key"}</Label>
                <Input
                  id="edit_api_key"
                  type="password"
                  value={editingModel.api_key || ""}
                  onChange={(e) =>
                    setEditingModel({ ...editingModel, api_key: e.target.value })
                  }
                  placeholder="留空保持不变"
                />
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <Switch
                    id="edit_supports_thinking"
                    checked={editingModel.supports_thinking || false}
                    onCheckedChange={(checked) =>
                      setEditingModel({ ...editingModel, supports_thinking: checked })
                    }
                  />
                  <Label htmlFor="edit_supports_thinking">{t.settings.models?.thinking || "支持思考"}</Label>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    id="edit_supports_vision"
                    checked={editingModel.supports_vision || false}
                    onCheckedChange={(checked) =>
                      setEditingModel({ ...editingModel, supports_vision: checked })
                    }
                  />
                  <Label htmlFor="edit_supports_vision">{t.settings.models?.vision || "支持视觉"}</Label>
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
              {t.common?.cancel || "取消"}
            </Button>
            <Button onClick={handleUpdateModel}>{t.common?.save || "保存"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </SettingsSection>
  );
}
