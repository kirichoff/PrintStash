import { getJson, sendAction, sendJson } from "@/lib/api/request";
import { CategoryCreate, CategoryRead, TagCreate, TagRead } from "@/types";

export function listCategories(): Promise<CategoryRead[]> {
  return getJson<CategoryRead[]>("/api/v1/categories");
}

export function createCategory(
  payload: CategoryCreate,
  apiKey?: string,
): Promise<CategoryRead> {
  return sendJson<CategoryRead>("/api/v1/categories", "POST", payload, apiKey);
}

export function deleteCategory(id: number, apiKey?: string): Promise<void> {
  return sendAction(`/api/v1/categories/${id}`, "DELETE", apiKey);
}

export function listTags(): Promise<TagRead[]> {
  return getJson<TagRead[]>("/api/v1/tags");
}

export function createTag(
  payload: TagCreate,
  apiKey?: string,
): Promise<TagRead> {
  return sendJson<TagRead>("/api/v1/tags", "POST", payload, apiKey);
}

export function deleteTag(id: number, apiKey?: string): Promise<void> {
  return sendAction(`/api/v1/tags/${id}`, "DELETE", apiKey);
}
