const EMBEDDING_MODEL_HINTS = [
  'embed', 'embedding', 'all-minilm', 'bge', 'mxbai', 'snowflake-arctic-embed',
  'nomic-embed', 'gte', 'e5', 'jina-embeddings', 'paraphrase-multilingual'
];

const IMAGE_MODEL_HINTS = ['flux', 'stable-diffusion', 'sdxl', 'imagen', 'dall-e'];

export const normalizeModelName = (model) => String(model || '').trim();

export const getModelBaseName = (model) => normalizeModelName(model).toLowerCase().split(':')[0];

export const isEmbeddingModel = (model) => {
  const normalized = normalizeModelName(model).toLowerCase();
  return EMBEDDING_MODEL_HINTS.some((hint) => normalized.includes(hint));
};

export const isImageModel = (model) => {
  const normalized = normalizeModelName(model).toLowerCase();
  return IMAGE_MODEL_HINTS.some((hint) => normalized.includes(hint));
};

export const isChatModel = (model) => !isEmbeddingModel(model) && !isImageModel(model);

export const uniqueSortedModels = (models) => {
  return Array.from(new Set((models || []).map(normalizeModelName).filter(Boolean)))
    .sort((left, right) => left.localeCompare(right, undefined, { sensitivity: 'base' }));
};

export const splitModelOptions = (models) => {
  const uniqueModels = uniqueSortedModels(models);
  return {
    chatModels: uniqueModels.filter(isChatModel),
    embeddingModels: uniqueModels.filter(isEmbeddingModel)
  };
};
