type ErrorStateProps = {
  text?: string;
};

export default function ErrorState({ text = "Something went wrong." }: ErrorStateProps) {
  return <p className="text-danger">{text}</p>;
}
