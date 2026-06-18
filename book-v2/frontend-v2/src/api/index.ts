// API 模块统一入口
// 所有 ../api 或 ./api 的 import 都由这里再导出到 client.ts 的实际实现
export { default as api, authAPI, bookAPI, ratingAPI, recommendAPI, aiAPI } from './client';
