type LoadingStateProps = {
  text?: string;
};

export default function LoadingState({ text = "Loading..." }: LoadingStateProps) {
  return <p className="text-secondary">{text}</p>;
}
