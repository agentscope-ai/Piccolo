/* Bounded model failures translated into recoverable, user-facing guidance. */
(() => {
  const messages = {
    hosted_model_not_configured: ['Piccolo is awaiting server configuration. You can connect your own model.', 'Piccolo 等待服务端配置，也可以连接你自己的模型。'],
    connection_failed: ['Cannot reach the model. Check the connection and local-network permission, then retry.', '无法连接模型，请检查连接和本地网络权限后重试。'],
    invalid_response: ['The model returned an invalid decision. Check the API format and served model name.', '模型返回的决策格式不正确，请检查接口类型与实际服务模型名。'],
    timeout: ['The model request timed out. Reduce request concurrency or retry after the service recovers.', '模型请求超时，请降低请求并发，或待服务恢复后重试。'],
    cancelled: ['The model request was cancelled. You can retry or continue manually.', '本次模型请求已取消，可以重试或继续手动操作。'],
    authentication_failed: ['The model rejected authentication. Check its API key and access permissions.', '模型鉴权失败，请检查 API key 和接口访问权限。'],
    rate_limited: ['The model is rate limited. Reduce request concurrency and try again shortly.', '模型服务限流，请降低请求并发并稍后重试。'],
    endpoint_not_found: ['The model endpoint was not found. Check the complete endpoint URL.', '模型接口不存在，请检查填写的完整接口地址。'],
    upstream_unavailable: ['The model service is unavailable. Check the connection and retry shortly.', '模型服务暂不可用，请检查连接并稍后重试。'],
  };
  function fromResponse(data, status) {
    const detail = data?.detail;
    const code = detail?.cause || detail?.code || ({401:'authentication_failed',429:'rate_limited',503:'upstream_unavailable',504:'timeout'})[status];
    const pair = messages[code];
    const message = pair ? (window.JevI18n?.t(...pair) ?? pair[0])
      : typeof detail === 'string' ? detail
      : (window.JevI18n?.t('The request failed. Please retry.', '请求未完成，请重试。') ?? 'The request failed. Please retry.');
    return Object.assign(new Error(message), {code, status});
  }
  window.JevGameErrors = Object.freeze({fromResponse});
})();
