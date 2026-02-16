interface AnnualRevenueInputProps {
  value?: string;
  onChange?: (value: string) => void;
  required?: boolean;
}

export const AnnualRevenueInput = ({
  value = '',
  onChange,
  required = false,
}: AnnualRevenueInputProps) => {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange?.(e.target.value);
  };

  return (
    <div>
      <label
        htmlFor="annual-revenue"
        className="block text-sm font-medium text-gray-700 mb-2"
      >
        Annual Revenue {required && <span className="text-red-500">*</span>}
      </label>
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <span className="text-gray-500 sm:text-sm">$</span>
        </div>
        <input
          type="text"
          id="annual-revenue"
          value={value}
          onChange={handleChange}
          placeholder="0.00"
          className="block w-full pl-7 pr-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
        />
      </div>
      <p className="mt-2 text-sm text-gray-500">
        Enter your company's annual revenue
      </p>
    </div>
  );
};

