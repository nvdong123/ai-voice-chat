interface Props {
  title: string;
  description?: string;
}

export default function PageHeader({ title, description }: Props) {
  return (
    <div className="mb-7">
      <h1 className="text-2xl font-bold tracking-tight text-gray-100">{title}</h1>
      {description && (
        <p className="mt-1.5 text-sm text-gray-500">{description}</p>
      )}
    </div>
  );
}
