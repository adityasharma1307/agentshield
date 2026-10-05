export function Loading({ label }: { label: string }) {
  return (
    <p className="state" role="status">
      {label}
    </p>
  );
}

export function Empty({ label }: { label: string }) {
  return <p className="state">{label}</p>;
}

export function Failure({ label }: { label: string }) {
  return (
    <p className="state error" role="alert">
      {label}
    </p>
  );
}
