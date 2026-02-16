interface TaxDesignationDropdownProps {
  value?: string;
  onChange?: (value: string) => void;
  required?: boolean;
}

const TAX_DESIGNATIONS = [
  { value: '', label: 'Select tax designation...' },
  { value: 'c_corp', label: 'C Corporation' },
  { value: 's_corp', label: 'S Corporation' },
  { value: 'general_partnership', label: 'General Partnership' },
  { value: 'limited_partnership', label: 'Limited Partnership (LP)' },
  { value: 'llp', label: 'Limited Liability Partnership (LLP)' },
  { value: 'llc_disregarded', label: 'LLC - Disregarded Entity (Single-member)' },
  { value: 'llc_partnership', label: 'LLC - Partnership (Multi-member default)' },
  { value: 'llc_c_corp', label: 'LLC - Taxed as C Corporation' },
  { value: 'llc_s_corp', label: 'LLC - Taxed as S Corporation' },
  { value: 'sole_proprietorship', label: 'Sole Proprietorship' },
  { value: 'nonprofit_501c3', label: 'Nonprofit - 501(c)(3)' },
  { value: 'nonprofit_501c_other', label: 'Nonprofit - Other 501(c) designation' },
  { value: 'government_entity', label: 'Government Entity' },
  { value: 'trust_estate', label: 'Trust or Estate' },
];

export const TaxDesignationDropdown = ({
  value = '',
  onChange,
  required = false,
}: TaxDesignationDropdownProps) => {
  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange?.(e.target.value);
  };

  return (
    <div>
      <label
        htmlFor="tax-designation"
        className="block text-sm font-medium text-gray-700 mb-2"
      >
        Tax Designation {required && <span className="text-red-500">*</span>}
      </label>
      <select
        id="tax-designation"
        value={value}
        onChange={handleChange}
        className="block w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
      >
        {TAX_DESIGNATIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <p className="mt-2 text-sm text-gray-500">
        Select your entity's tax classification
      </p>
    </div>
  );
};

