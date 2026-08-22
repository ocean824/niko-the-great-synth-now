import * as DocumentPicker from "expo-document-picker";
import * as FileSystem from "expo-file-system/legacy";

import { synthNowApi, type AnalysisStatus } from "@/lib/synth-now-api";

export type SelectedAudio = DocumentPicker.DocumentPickerAsset & {
  inputType: "mix" | "stem";
};

const MAX_UPLOAD_BYTES = 25_000_000;

export async function selectAuthorizedAudio(inputType: "mix" | "stem"): Promise<SelectedAudio | null> {
  const result = await DocumentPicker.getDocumentAsync({
    type: "audio/*",
    copyToCacheDirectory: true,
    multiple: false,
  });

  if (result.canceled) return null;
  const asset = result.assets[0];

  if (asset.size && asset.size > MAX_UPLOAD_BYTES) {
    throw new Error("This file is larger than the current 25 MB authorized analysis limit.");
  }

  return { ...asset, inputType };
}

export async function uploadForAnalysis(asset: SelectedAudio, token?: string | null): Promise<AnalysisStatus> {
  const grant = await synthNowApi.createUpload(
    {
      filename: asset.name,
      mimeType: asset.mimeType || "audio/octet-stream",
      sizeBytes: asset.size,
      inputType: asset.inputType,
    },
    token,
  );

  if (asset.size && asset.size > grant.constraints.maxBytes) {
    throw new Error("This file is larger than the limit approved by the server.");
  }

  const response = await FileSystem.uploadAsync(grant.upload.url, asset.uri, {
    httpMethod: "PUT",
    uploadType: FileSystem.FileSystemUploadType.BINARY_CONTENT,
    headers: grant.upload.headers,
  });

  if (response.status < 200 || response.status >= 300) {
    throw new Error("The private upload did not complete. Please try again.");
  }

  return synthNowApi.completeUpload(grant.jobId, { sizeBytes: asset.size }, token);
}
