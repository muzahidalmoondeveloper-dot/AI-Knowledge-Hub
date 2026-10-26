export type Row = { id: string; name: string; [key: string]: any };
export type User = { id: string; email: string; role: string };
export type Source = {
  source_id: string;
  document_id: string;
  title: string;
  page: number | null;
  excerpt: string;
  score: number;
};
export type Message = {
  id: string;
  role: string;
  content: string;
  status: string;
  sources: Source[];
};
