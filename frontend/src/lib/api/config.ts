import { getJson, sendAction, sendJson } from "@/lib/api/request";
import {
  MakerWorldLoginRequest,
  MakerWorldLoginResponse,
  MakerWorldStatus,
  MakerWorldTokenRequest,
  MakerWorldVerifyRequest,
  SetupRequest,
  SetupResponse,
  SetupStatus,
  VaultConfigRead,
  VaultConfigUpdate,
} from "@/types";

export function getSetupStatus(): Promise<SetupStatus> {
  return getJson<SetupStatus>("/api/v1/setup/status");
}

export function completeSetup(body: SetupRequest): Promise<SetupResponse> {
  return sendJson<SetupResponse>("/api/v1/setup", "POST", body);
}

export function getVaultConfig(): Promise<VaultConfigRead> {
  return getJson<VaultConfigRead>("/api/v1/config");
}

export function updateVaultConfig(body: VaultConfigUpdate): Promise<VaultConfigRead> {
  return sendJson<VaultConfigRead>("/api/v1/config", "PUT", body);
}

export function getMakerWorldStatus(): Promise<MakerWorldStatus> {
  return getJson<MakerWorldStatus>("/api/v1/config/makerworld");
}

export function makerWorldLogin(
  body: MakerWorldLoginRequest,
): Promise<MakerWorldLoginResponse> {
  return sendJson<MakerWorldLoginResponse>(
    "/api/v1/config/makerworld/login",
    "POST",
    body,
  );
}

export function makerWorldVerify(
  body: MakerWorldVerifyRequest,
): Promise<MakerWorldLoginResponse> {
  return sendJson<MakerWorldLoginResponse>(
    "/api/v1/config/makerworld/verify",
    "POST",
    body,
  );
}

export function makerWorldSetToken(
  body: MakerWorldTokenRequest,
): Promise<MakerWorldStatus> {
  return sendJson<MakerWorldStatus>(
    "/api/v1/config/makerworld/token",
    "POST",
    body,
  );
}

export function makerWorldDisconnect(): Promise<void> {
  return sendAction("/api/v1/config/makerworld", "DELETE");
}
