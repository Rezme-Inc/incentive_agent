interface TotalEmployeesInputProps {
  value?: string;
  onChange?: (value: string) => void;
  required?: boolean;
}

export const TotalEmployeesInput = ({
  value = '',
  onChange,
  required = false,
}: TotalEmployeesInputProps) => {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange?.(e.target.value);
  };

  return (
    <div>
      <label
        htmlFor="total-employees"
        className="block text-sm font-medium text-gray-700 mb-2"
      >
        Total Employees {required && <span className="text-red-500">*</span>}
      </label>
      <input
        type="number"
        id="total-employees"
        value={value}
        onChange={handleChange}
        placeholder="0"
        min="0"
        className="block w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
      />
      <p className="mt-2 text-sm text-gray-500">
        Enter the total number of employees
      </p>
    </div>
  );
};

